# Инструменты и сторонние компоненты

- Gradle Wrapper 8.9: Gradle, Apache License 2.0. https://github.com/gradle/gradle/tree/v8.9.0
- Android SDK Platform 35 и Build Tools 35.0.0 используются для сборки; их дистрибутивы в комплект не включены. https://developer.android.com/studio
- Eclipse ECJ 3.39.0 использован как Java-компилятор при сборке в Cloud; его JAR в комплект не включён. https://eclipse.dev/jdt/core/
- Playwright 1.62.1 и Chromium использованы для браузерных тестов. Дистрибутивы браузера в комплект не включены. https://playwright.dev/
- JSON-java 20240303 используется только при JVM-тестах правил напоминаний; в APK применяется системный Android org.json. https://github.com/stleary/JSON-java
- Веб-интерфейс основан на предоставленных пользователем HTML-файлах.
