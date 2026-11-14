-- Run as the project owner in Supabase SQL Editor. No service-role key is required in the app.
-- This script creates only Temoraxis objects and never drops user documents.
begin;
create schema if not exists temoraxis_private;
revoke all on schema temoraxis_private from public, anon, authenticated;

create table if not exists temoraxis_private.config (
    id boolean primary key default true check (id), invite_hash bytea
);
insert into temoraxis_private.config(id) values(true) on conflict do nothing;
revoke all on temoraxis_private.config from public, anon, authenticated;

create table if not exists public.temoraxis_members (
    user_id uuid primary key references auth.users(id) on delete cascade,
    joined_at timestamptz not null default now()
);
create table if not exists public.temoraxis_documents (
    user_id uuid primary key references auth.users(id) on delete cascade,
    revision bigint not null check (revision > 0),
    document jsonb not null,
    updated_at timestamptz not null default now()
);
alter table public.temoraxis_members enable row level security;
alter table public.temoraxis_documents enable row level security;
revoke all on public.temoraxis_members,public.temoraxis_documents from public,anon,authenticated;
grant usage on schema public to authenticated;
grant select on public.temoraxis_members,public.temoraxis_documents to authenticated;
drop policy if exists temoraxis_own_membership on public.temoraxis_members;
create policy temoraxis_own_membership on public.temoraxis_members for select to authenticated
    using (user_id = (select auth.uid()));
drop policy if exists temoraxis_own_document on public.temoraxis_documents;
create policy temoraxis_own_document on public.temoraxis_documents for select to authenticated
    using (user_id = (select auth.uid()) and exists (
        select 1 from public.temoraxis_members m where m.user_id = (select auth.uid())
    ));

-- Owner-only helper: first execution creates a code; repeat execution does not rotate it.
-- Explicit rotation: select temoraxis_private.admin_invite_code(true);
create or replace function temoraxis_private.admin_invite_code(p_rotate boolean default false)
returns text language plpgsql security definer set search_path = '' as $$
declare code text;
begin
    perform 1 from temoraxis_private.config where id=true for update;
    if not p_rotate and exists(select 1 from temoraxis_private.config where id=true and invite_hash is not null) then
        return null;
    end if;
    code := replace(pg_catalog.gen_random_uuid()::text || pg_catalog.gen_random_uuid()::text,'-','');
    update temoraxis_private.config set invite_hash=pg_catalog.sha256(pg_catalog.convert_to(code,'UTF8')) where id=true;
    return code;
end;
$$;
revoke all on function temoraxis_private.admin_invite_code(boolean) from public,anon,authenticated;

create or replace function public.temoraxis_join(p_invite_code text default '')
returns boolean language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid();
begin
    if uid is null then raise exception using errcode='42501',message='Требуется вход в аккаунт.'; end if;
    if exists(select 1 from public.temoraxis_members m where m.user_id=uid) then return true; end if;
    if p_invite_code is null or length(p_invite_code)<16 or length(p_invite_code)>256 or not exists(
        select 1 from temoraxis_private.config where id=true
        and invite_hash=pg_catalog.sha256(pg_catalog.convert_to(p_invite_code,'UTF8'))
    ) then raise exception using errcode='42501',message='Неверный код приглашения.'; end if;
    insert into public.temoraxis_members(user_id) values(uid) on conflict do nothing;
    return true;
end;
$$;
revoke all on function public.temoraxis_join(text) from public,anon,authenticated;
grant execute on function public.temoraxis_join(text) to authenticated;

create or replace function temoraxis_private.valid_document(doc jsonb)
returns boolean language plpgsql immutable set search_path = '' as $$
declare item jsonb; group_item jsonb; link_item jsonb;
begin
    if doc is null or jsonb_typeof(doc)<>'object' or octet_length(doc::text)>5242880 then return false; end if;
    if (select count(*) from jsonb_object_keys(doc))<>5 or not(doc ?& array['tasks','clock','specialDates','tags','startPage']) then return false; end if;
    if jsonb_typeof(doc->'tasks')<>'array' or jsonb_typeof(doc->'clock')<>'object'
        or jsonb_typeof(doc->'specialDates')<>'array' or jsonb_typeof(doc->'tags')<>'array' then return false; end if;
    if jsonb_array_length(doc->'tasks')>10000 then return false; end if;
    if (select count(*) from jsonb_array_elements(doc->'tasks'))<>(select count(distinct t->>'id') from jsonb_array_elements(doc->'tasks') t) then return false; end if;
    for item in select value from jsonb_array_elements(doc->'tasks') loop
        if jsonb_typeof(item)<>'object' or jsonb_typeof(item->'id') is distinct from 'string'
            or (item->>'id')!~'^[A-Za-z0-9_-]{1,128}$' or jsonb_typeof(item->'title') is distinct from 'string' then return false; end if;
    end loop;
    for item in select value from jsonb_array_elements(doc->'tags') loop
        if jsonb_typeof(item)<>'string' then return false; end if;
    end loop;
    for item in select value from jsonb_array_elements(doc->'specialDates') loop
        if jsonb_typeof(item->'name') is distinct from 'string' or jsonb_typeof(item->'date') is distinct from 'string' then return false; end if;
    end loop;
    if doc->'startPage'<>'null'::jsonb then
        if jsonb_typeof(doc->'startPage'->'groups') is distinct from 'array' then return false; end if;
        for group_item in select value from jsonb_array_elements(doc->'startPage'->'groups') loop
            if jsonb_typeof(group_item->'id') is distinct from 'string' or (group_item->>'id')!~'^[A-Za-z0-9_-]{1,128}$'
                or jsonb_typeof(group_item->'name') is distinct from 'string' or jsonb_typeof(group_item->'links') is distinct from 'array' then return false; end if;
            for link_item in select value from jsonb_array_elements(group_item->'links') loop
                if jsonb_typeof(link_item->'id') is distinct from 'string' or (link_item->>'id')!~'^[A-Za-z0-9_-]{1,128}$'
                    or jsonb_typeof(link_item->'name') is distinct from 'string' or jsonb_typeof(link_item->'url') is distinct from 'string'
                    or (link_item->>'url')!~*'^https?://' then return false; end if;
            end loop;
        end loop;
    end if;
    return true;
exception when others then return false;
end;
$$;
revoke all on function temoraxis_private.valid_document(jsonb) from public,anon,authenticated;

-- Only this function writes documents: user identity comes from the JWT, never from request data.
-- A conditional UPDATE/INSERT makes concurrent writes atomic. No client gets direct write privileges.
create or replace function public.temoraxis_push(p_expected_revision bigint,p_document jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); rev bigint; changed timestamptz;
begin
    if uid is null or not exists(select 1 from public.temoraxis_members m where m.user_id=uid) then
        raise exception using errcode='42501',message='Нет доступа к синхронизации. Проверьте код приглашения.';
    end if;
    if p_expected_revision is null or p_expected_revision<0 or p_expected_revision>9007199254740990
        or not temoraxis_private.valid_document(p_document) then
        raise exception using errcode='22023',message='Некорректные данные синхронизации.';
    end if;
    if p_expected_revision=0 then
        insert into public.temoraxis_documents(user_id,revision,document,updated_at)
            values(uid,1,p_document,clock_timestamp()) on conflict do nothing returning revision,updated_at into rev,changed;
    else
        update public.temoraxis_documents set revision=revision+1,document=p_document,updated_at=clock_timestamp()
            where user_id=uid and revision=p_expected_revision returning revision,updated_at into rev,changed;
    end if;
    if rev is null then
        select revision into rev from public.temoraxis_documents where user_id=uid;
        return jsonb_build_object('conflict',true,'revision',coalesce(rev,0));
    end if;
    return jsonb_build_object('revision',rev,'updated',extract(epoch from changed)::bigint);
end;
$$;
revoke all on function public.temoraxis_push(bigint,jsonb) from public,anon,authenticated;
grant execute on function public.temoraxis_push(bigint,jsonb) to authenticated;
notify pgrst,'reload schema';
commit;
-- Keep the returned invitation code private; enter it in Temoraxis on the first login.
select temoraxis_private.admin_invite_code() as invitation_code;
