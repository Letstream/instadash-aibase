# Mobile scaffold — project & platform files

> Part of the [mobile scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the mobile repo root (`mobile/`).

Replaces what `flutter create` generated for these paths (pubspec, lint config, `.gitignore`,
Android signing + manifests) and adds the l10n config, the dart-define example and the signing
template. Everything else from `flutter create` (`ios/`, the rest of `android/`) stays as generated.

After writing these: set the iOS display name (`ios/Runner/Info.plist` → `CFBundleDisplayName` =
`<Project name>`) and delete the generated `test/widget_test.dart`.

### `pubspec.yaml`

Versions are the ones the scaffold was verified with; keep the caret ranges.

```yaml
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

name: <project_slug>
description: "<Project name> mobile app."
publish_to: "none"

# <marketing version>+<build number>. Bump the build number on every store upload
# (see docs/architecture-guidelines/mobile/build-and-release.md).
version: 0.1.0+1

environment:
  sdk: ^3.12.0
  flutter: ">=3.44.0"

dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  cupertino_icons: ^1.0.8
  dio: ^5.11.1
  flutter_secure_storage: ^11.2.0
  flutter_timezone: ^5.1.0
  go_router: ^17.5.0
  intl: ^0.20.2
  provider: ^6.1.5+1
  shared_preferences: ^2.5.5

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^6.0.0
  mocktail: ^1.0.5

flutter:
  uses-material-design: true
  generate: true
```

### `analysis_options.yaml`

Strict analyzer + extra lints; `formatter.page_width` drives `dart format`. The gate runs `flutter analyze --fatal-infos`, so infos fail too.

```yaml
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

include: package:flutter_lints/flutter.yaml

formatter:
  page_width: 100

analyzer:
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true
  errors:
    missing_required_param: error
    missing_return: error
    must_be_immutable: error
  exclude:
    - "lib/l10n/app_localizations*.dart"
    - "build/**"

linter:
  rules:
    - always_declare_return_types
    - always_use_package_imports
    - avoid_dynamic_calls
    - avoid_print
    - avoid_slow_async_io
    - avoid_type_to_string
    - cancel_subscriptions
    - close_sinks
    - directives_ordering
    - prefer_const_constructors
    - prefer_const_declarations
    - prefer_final_fields
    - prefer_final_locals
    - prefer_single_quotes
    - sort_child_properties_last
    - test_types_in_equals
    - throw_in_finally
    - unawaited_futures
    - unnecessary_await_in_return
    - unnecessary_lambdas
    - unnecessary_parenthesis
    - use_build_context_synchronously
    - use_super_parameters
```

### `l10n.yaml`

`flutter pub get` / `flutter run` regenerate `lib/l10n/app_localizations*.dart` from the ARB files (commit them; never edit).

```yaml
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
output-class: AppLocalizations
nullable-getter: false
```

### `.gitignore`

`flutter create`'s ignores plus signing material, per-env config and platform service files.

```gitignore
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

# Miscellaneous
*.class
*.log
*.pyc
*.swp
.DS_Store
.atom/
.build/
.buildlog/
.history
.svn/
.swiftpm/
migrate_working_dir/

# IntelliJ related
*.iml
*.ipr
*.iws
.idea/

# The .vscode folder contains launch configuration and tasks you configure in
# VS Code which you may wish to be included in version control, so this line
# is commented out by default.
#.vscode/

# Flutter/Dart/Pub related
**/doc/api/
**/ios/Flutter/.last_build_id
.dart_tool/
.flutter-plugins-dependencies
.pub-cache/
.pub/
/build/
/coverage/

# Symbolication related
app.*.symbols

# Obfuscation related
app.*.map.json

# Android Studio will place build artifacts here
/android/app/debug
/android/app/profile
/android/app/release

# Signing & secrets — never commit (CI writes them from its secret store)
/android/key.properties
*.jks
*.keystore
*.p12
*.mobileprovision
*.p8
# Per-environment dart-define files (public values, but kept out of git like .env)
/config/*.json
!/config/example.json
# Firebase / service config files, if a project adds them
google-services.json
GoogleService-Info.plist
# Coverage
/coverage/
```

### `config/example.json`

Copy to `config/dev.json` (and `staging.json` / `prod.json`, all gitignored) and fill from `DOCS.md`. Values are compiled into the app — public identifiers only, never secrets. JSON cannot hold the license header.

```json
{
  "APP_ENV": "dev",
  "APP_NAME": "<Project name>",
  "LEGAL_ENTITY_NAME": "<Legal entity name>",
  "API_BASE_URL": "http://10.0.2.2:<BACKEND_PORT>/api/",
  "TENANCY_MODE": "multi"
}
```

### `android/app/build.gradle.kts`

Release signing from the gitignored `android/key.properties`; without it, local release builds fall back to debug signing.

```kotlin
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing comes from android/key.properties (gitignored; see key.properties.example).
// CI writes that file and the keystore from its secret store. Neither is ever committed.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKeystore = keystorePropertiesFile.exists()
if (hasReleaseKeystore) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "<org_reverse_domain>.<project_slug>"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "<org_reverse_domain>.<project_slug>"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // Without key.properties a local release build is debug-signed (runnable, not
            // uploadable). Store builds always run where key.properties exists.
            signingConfig =
                if (hasReleaseKeystore) signingConfigs.getByName("release")
                else signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
```

### `android/key.properties.example`

Template for the release machine / CI. The real `key.properties` and the keystore are never committed.

```properties
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

# Copy to android/key.properties (gitignored) on a release machine / in CI. Never commit
# the real file or the keystore. storeFile is relative to android/app/.
storePassword=<from the secret store>
keyPassword=<from the secret store>
keyAlias=upload
storeFile=../upload-keystore.jks
```

### `android/app/src/main/AndroidManifest.xml`

Adds the `INTERNET` permission (release builds need it) and disables Android backup (encrypted secure-storage prefs must not be restored onto another device).

```xml
<!--
  <Project Name>
  Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
  Author: <Legal Entity Name>

  Built on Instadash AI Base by Letstream
  (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
  Template portions (c) Letstream Ventures Pvt Ltd.

  The Instadash AI Base template is provided "AS IS", without warranty of any
  kind, express or implied, including merchantability, fitness for a particular
  purpose and non-infringement, unless covered by an explicit written agreement
  with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
  redistribution of the template, in whole or in part, is prohibited and may
  result in legal action and remedies available under applicable law.
-->
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- Release builds need this; Flutter only adds it to debug/profile by default. -->
    <uses-permission android:name="android.permission.INTERNET"/>
    <application
        android:label="<Project name>"
        android:allowBackup="false"
        android:fullBackupContent="false"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:taskAffinity=""
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            <!-- Specifies an Android theme to apply to this Activity as soon as
                 the Android process has started. This theme is visible to the user
                 while the Flutter UI initializes. After that, this theme continues
                 to determine the Window background behind the Flutter UI. -->
            <meta-data
              android:name="io.flutter.embedding.android.NormalTheme"
              android:resource="@style/NormalTheme"
              />
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <!-- Don't delete the meta-data below.
             This is used by the Flutter tool to generate GeneratedPluginRegistrant.java -->
        <meta-data
            android:name="flutterEmbedding"
            android:value="2" />
    </application>
    <!-- Required to query activities that can process text, see:
         https://developer.android.com/training/package-visibility and
         https://developer.android.com/reference/android/content/Intent#ACTION_PROCESS_TEXT.

         In particular, this is used by the Flutter engine in io.flutter.plugin.text.ProcessTextPlugin. -->
    <queries>
        <intent>
            <action android:name="android.intent.action.PROCESS_TEXT"/>
            <data android:mimeType="text/plain"/>
        </intent>
    </queries>
</manifest>
```

### `android/app/src/debug/AndroidManifest.xml`

Debug-only cleartext so the emulator can reach `http://10.0.2.2:<BACKEND_PORT>/api/`.

```xml
<!--
  <Project Name>
  Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
  Author: <Legal Entity Name>

  Built on Instadash AI Base by Letstream
  (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
  Template portions (c) Letstream Ventures Pvt Ltd.

  The Instadash AI Base template is provided "AS IS", without warranty of any
  kind, express or implied, including merchantability, fitness for a particular
  purpose and non-infringement, unless covered by an explicit written agreement
  with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
  redistribution of the template, in whole or in part, is prohibited and may
  result in legal action and remedies available under applicable law.
-->
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- The INTERNET permission is required for development. Specifically,
         the Flutter tool needs it to communicate with the running application
         to allow setting breakpoints, to provide hot reload, etc.
    -->
    <uses-permission android:name="android.permission.INTERNET"/>
    <!-- Debug only: allow http:// to the local backend (e.g. http://10.0.2.2:<port>/api/).
         Release builds keep Android's cleartext block, so non-dev APIs must be https. -->
    <application android:usesCleartextTraffic="true"/>
</manifest>
```
