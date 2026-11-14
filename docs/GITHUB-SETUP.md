# GitHub: постоянная страница и автоматические обновления

Страница пользователей: **https://dfkzg.github.io/Temoraxis/**.

Она показывает последний опубликованный релиз и ведёт непосредственно к APK. Учётная запись GitHub для скачивания из публичного репозитория не нужна. Сам GitHub Pages не синхронизирует задачи: сервер из `server/` размещается отдельно.

## Один раз: включить Pages

В репозитории откройте **Settings → Pages → Build and deployment → Source → GitHub Actions**.

Workflow `Download page` публикует `dist/pages`, созданный `tools/prepare_pages.py` из страницы, sitemap и общих иконок. Технические инструкции из `docs/` в сайт не попадают. Ключей или личных данных в публичной сборке нет.

## Один раз: сохранить существующий ключ APK

Чтобы обновления устанавливались поверх APK 0.1.0/0.1.1, используется тот же ключ. В публичном репозитории есть только отпечаток сертификата `android/signing-certificate.sha256`. Самого ключа в Git нет.

В **Settings → Secrets and variables → Actions → New repository secret** добавьте:

- Name: `ANDROID_KEYSTORE_BASE64`
- Secret: Base64-представление существующего keystore, которое передаётся владельцу отдельно.

Прежний тестовый keystore использует стандартные alias/password Android debug key. Workflow уже содержит соответствующие значения по умолчанию. Если пароли или alias будут изменены с сохранением самого ключа, задайте дополнительные secrets `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_PASSWORD`, `ANDROID_KEY_ALIAS`.

Не вставляйте Base64 ключа в issues, README, исходники, публичную страницу скачивания или сообщения коммитов. После установки secret GitHub не показывает его значение.

Если доступа к Secrets нет у подключённого приложения, этот шаг выполняет владелец репозитория в веб-интерфейсе. Передача ключа владельцу и установка secret не меняют сертификат APK.

## Выпустить новую версию

1. Обновить версию и versionCode в `release.json`, обоих AndroidManifest, `android/app/build.gradle`, `package.json` и `package-lock.json`.
2. Описать изменения в `CHANGELOG.md`.
3. Загрузить изменения в `main`.
4. Создать тег `vX.Y.Z` на готовом коммите либо запустить **Actions → Publish Android release → Run workflow**.

Проверки выполнятся до сборки. При ошибке, отсутствии ключа или несовпадении сертификата несовместимый APK не публикуется.

Workflow сначала создаёт черновик релиза, загружает APK, ZIP и контрольные суммы, затем публикует релиз целиком. Уже опубликованная версия не перезаписывается — для изменения нужен следующий номер.

Страница обновляется по данным последнего релиза автоматически. Изменять её HTML после каждого APK не нужно. Если GitHub API временно недоступен, прямая кнопка последнего APK продолжает работать.

## Локальный выпуск

```
python stage_web.py
python tools/prepare_release.py --validate-only
python android/build.py --sdk PATH_TO_SDK --keystore PATH_TO_PRIVATE_KEY --output dist/temoraxis-android.apk
python tools/check_signing.py dist/temoraxis-android.apk --sdk PATH_TO_SDK
python tools/prepare_release.py
```

Для ключа с нестандартными паролями используйте переменные окружения; не помещайте пароль в аргументы команды. `dist/`, keystore и базы данных исключены из Git.

Первый публичный релиз допускается собрать локально тем же ключом и загрузить в Releases. После однократной настройки Secrets дальнейшую сборку выполняет GitHub Actions.
