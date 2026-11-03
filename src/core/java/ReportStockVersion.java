// morphe-builder: the Morphe code inside an app must see the app's real version.
//
// A build's versionName carries the patch number (21.30.216.2.0.0), because that is what ObtainX compares with the update
// page. Morphe's own code reads the same versionName, and compares it with the recommended version: anything longer than
// "21.30.216" is "newer", so a stable build opened with "Experimental Alert". It also sends that name to YouTube as the client
// version. This makes Morphe's two readers answer with the app's real version, and leaves everything else alone.
//
// Run with the Morphe CLI jar on the class path, which holds dexlib2: java -cp cli.jar ReportStockVersion.java in out version
// Prints the number of methods changed; writes out only when it is above 0.
//
// Licensed under the GNU GPLv3, like the rest of this repository.

import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcode;
import com.android.tools.smali.dexlib2.builder.MutableMethodImplementation;
import com.android.tools.smali.dexlib2.builder.instruction.BuilderInstruction11x;
import com.android.tools.smali.dexlib2.builder.instruction.BuilderInstruction21c;
import com.android.tools.smali.dexlib2.dexbacked.DexBackedDexFile;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.Method;
import com.android.tools.smali.dexlib2.iface.MethodImplementation;
import com.android.tools.smali.dexlib2.immutable.ImmutableClassDef;
import com.android.tools.smali.dexlib2.immutable.ImmutableMethod;
import com.android.tools.smali.dexlib2.immutable.reference.ImmutableStringReference;
import com.android.tools.smali.dexlib2.writer.io.FileDataStore;
import com.android.tools.smali.dexlib2.writer.pool.DexPool;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class ReportStockVersion {
    private static final String UTILS = "Lapp/morphe/extension/shared/Utils;";
    private static final String SPOOF = "Lapp/morphe/extension/shared/spoof/SpoofAppVersionPatch;";
    private static int changed = 0;

    private static MethodImplementation answerWith(Method method, String version) {
        // Utils.getAppVersionName(): return the version.
        MethodImplementation old = method.getImplementation();
        MutableMethodImplementation code = new MutableMethodImplementation(Math.max(old.getRegisterCount(), 1));
        code.addInstruction(new BuilderInstruction21c(Opcode.CONST_STRING, 0, new ImmutableStringReference(version)));
        code.addInstruction(new BuilderInstruction11x(Opcode.RETURN_OBJECT, 0));
        return code;
    }

    private static MethodImplementation replaceArgument(Method method, String version) {
        // SpoofAppVersionPatch.getUniversalAppVersionOverride(version): the patch's own setting still wins; only the
        // version it was handed changes. The only argument of a static method is the last register.
        MutableMethodImplementation code = new MutableMethodImplementation(method.getImplementation());
        int argument = method.getImplementation().getRegisterCount() - 1;
        code.addInstruction(0, new BuilderInstruction21c(Opcode.CONST_STRING, argument, new ImmutableStringReference(version)));
        return code;
    }

    private static ClassDef rewrite(ClassDef cls, String version) {
        boolean utils = cls.getType().equals(UTILS);
        if (!utils && !cls.getType().equals(SPOOF)) {
            return cls;
        }
        List<Method> methods = new ArrayList<>();
        for (Method method : cls.getMethods()) {
            MethodImplementation code = null;
            if (utils && method.getName().equals("getAppVersionName") && method.getParameterTypes().isEmpty()) {
                code = answerWith(method, version);
            } else if (!utils && method.getName().equals("getUniversalAppVersionOverride") && method.getParameterTypes().size() == 1) {
                code = replaceArgument(method, version);
            }
            if (code == null) {
                methods.add(method);
                continue;
            }
            changed++;
            methods.add(new ImmutableMethod(method.getDefiningClass(), method.getName(), method.getParameters(),
                    method.getReturnType(), method.getAccessFlags(), method.getAnnotations(),
                    method.getHiddenApiRestrictions(), code));
        }
        return new ImmutableClassDef(cls.getType(), cls.getAccessFlags(), cls.getSuperclass(), cls.getInterfaces(),
                cls.getSourceFile(), cls.getAnnotations(), cls.getFields(), methods);
    }

    public static void main(String[] args) throws Exception {
        DexBackedDexFile dex = DexFileFactory.loadDexFile(new File(args[0]), null);
        DexPool pool = new DexPool(dex.getOpcodes());
        for (ClassDef cls : dex.getClasses()) {
            pool.internClass(rewrite(cls, args[2]));
        }
        if (changed > 0) {
            pool.writeTo(new FileDataStore(new File(args[1])));
        }
        System.out.println(changed);
    }
}
