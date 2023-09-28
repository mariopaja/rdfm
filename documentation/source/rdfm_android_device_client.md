# RDFM Android Device Client

## Introduction

The RDFM Android Device Client allows for integrating an Android-based device with the RDFM server.
Currently, only OTA update functionality is implemented.

## Integrating the app

This app is **not meant to be built separately** (i.e in Android Studio), but as part of the source tree for an existing device.
The app integrates with the Android UpdateEngine to perform the actual update installation, which requires it to be a system app.
Some configuration is required to the existing system sources.

### Copying the sources

First, copy the sources of the app to the root directory of the AOSP source tree.
After cloning this repository, run the following:
```
mkdir -v -p <path-to-aosp-tree>/vendor/antmicro/rdfm
cd devices/android-client/
cp -r app/src/main/* <path-to-aosp-tree>
```

### Configuring the device Makefile

The [product Makefile](https://source.android.com/docs/setup/create/new-device#build-a-product) must be configured to build the RDFM app into the system image.
To do this, add `rdfm` to the `PRODUCT_PACKAGES` variable in the target device Makefile:
```
PRODUCT_PACKAGES += rdfm
```

### Building the app

Afterwards, [the usual Android build procedure](https://source.android.com/docs/setup/build/building) can be used to build just the app.
From an already configured build environment, run:
```
mma rdfm
```
The resulting signed APK is in `out/target/product/<product-name>/system/app/rdfm/rdfm.apk`.

## System versioning

The app performs update check requests to the configured RDFM server.
The build version and device type are retrieved from the system properties:
- `ro.build.version.incremental` - the current software version (matches `rdfm.software.version`)
- `ro.build.product` - device type (matches `rdfm.hardware.devtype`)

When uploading an OTA package to the RDFM server, currently these values must be **manually** extracted from the update package, and passed as arguments to `rdfm-mgmt`:
```
rdfm-mgmt packages upload --path ota.zip --version <ro.build.version.incremental> --device <ro.build.product>
```

You can extract the values from the [package metadata file](https://source.android.com/docs/core/ota/tools#ota-package-metadata) by unzipping the OTA package.

## Configuring the app

The application will automatically start on system boot.
Available configuration options are shown below.

### Changing the default server address

You can change the default RDFM server address the app will connect to in the `app/src/main/res/xml/shared_preference.xml` file.
An example is shown below:

```xml
<!-- ... -->
        <EditTextPreference
            android:key="ota_server_address"
            android:title="server address"
            android:defaultValue="https://rdfm.example.com/"/>
<!-- ... -->
```

### Update check interval

Currently, the app has a hardcoded update check interval of 4 minutes.
This will be extended in the future to allow configuring it in a similar way as shown above in the server address case.

## Development

The provided Gradle files can be used for development purposes, simply open the `devices/android-client` directory in Android Studio.
Missing references to the `UpdateEngine` class are expected, but they do not prevent regular use of the IDE.

Do note however that **the app is not buildable from Android Studio**, as it requires integration with the aforementioned system API.
To test the app, an existing system source tree must be used.
Copy the modified sources to the AOSP tree, and re-run the [application build](#building-the-app).
The modified APK can then be uploaded to the device via ADB by running:
```
adb install <path-to-rdfm.apk>
```

### Restarting the app

With the target device connected via ADB, run:
```
adb shell am force-stop com.antmicro.update.rdfm
adb shell am start -n com.antmicro.update.rdfm/.MainActivity
```

### Fetching app logs

To view the application logs, run:
```
adb logcat --pid=`adb shell pidof -s com.antmicro.update.rdfm`
```