#!/usr/bin/env bash
set -e
cd /mnt/e/AI/H700Android/work/cubexx-build/ffvib
AJ=/mnt/d/AI/android-sdk/platforms/android-36/android.jar
D8=/mnt/d/AI/android-sdk/build-tools/35.0.0/lib/d8.jar
rm -rf classes dexout ffvib.jar; mkdir -p classes dexout
javac -source 8 -target 8 -bootclasspath "$AJ" -d classes FfVib.java 2>&1 | grep -vi "obsolete\|deprecat\|warning" || true
java -cp "$D8" com.android.tools.r8.D8 --min-api 29 --lib "$AJ" --output dexout classes/FfVib.class
(cd dexout && jar cf ../ffvib.jar classes.dex)
echo "jar bytes: $(stat -c %s ffvib.jar)"