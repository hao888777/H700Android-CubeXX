import android.hardware.input.InputManager;
import android.view.InputDevice;
import android.os.VibrationEffect;
import android.os.Vibrator;

public class FfVib {
    public static void main(String[] args) throws Exception {
        int ms = args.length > 0 ? Integer.parseInt(args[0]) : 3000;
        if (ms < 100) ms = 100;
        if (ms > 10000) ms = 10000;
        // Vibrator base ctor needs ActivityThread.getSystemContext(); bare
        // app_process has none -> prepare looper + establish system context.
        android.os.Looper.prepareMainLooper();
        Class.forName("android.app.ActivityThread").getMethod("systemMain").invoke(null);
        InputManager im = (InputManager) Class.forName("android.hardware.input.InputManager")
                .getMethod("getInstance").invoke(null);
        boolean hit = false;
        for (int id : im.getInputDeviceIds()) {
            InputDevice dev = im.getInputDevice(id);
            if (dev == null) continue;
            String name = dev.getName();
            if (name == null || !name.contains("ANBERNIC")) {
                System.out.println("id=" + id + " name=" + name + " (skip)");
                continue;
            }
            Vibrator v = dev.getVibrator();
            boolean has = v != null && v.hasVibrator();
            System.out.println("id=" + id + " name=" + name + " hasVibrator=" + has);
            if (has) {
                hit = true;
                System.out.println(">>> vibrating " + name + " " + ms + "ms (input FF path)");
                System.out.flush();
                v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
                Thread.sleep(ms + 500);
                System.out.println(">>> done. Feel the device: did it physically vibrate?");
            }
        }
        if (!hit) System.out.println("!! no ANBERNIC input vibrator found");
    }
}