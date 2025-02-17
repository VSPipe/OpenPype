import os
import platform


def add_implementation_envs(env, _app):
    # Add requirements to NUKE_PATH
    pype_root = os.environ["OPENPYPE_REPOS_ROOT"]
    new_nuke_paths = [
        os.path.join(pype_root, "openpype", "hosts", "nuke", "startup")
    ]
    old_nuke_path = env.get("NUKE_PATH") or ""
    for path in old_nuke_path.split(os.pathsep):
        if not path:
            continue

        norm_path = os.path.normpath(path)
        if norm_path not in new_nuke_paths:
            new_nuke_paths.append(norm_path)

    env["NUKE_PATH"] = os.pathsep.join(new_nuke_paths)
    env.pop("QT_AUTO_SCREEN_SCALE_FACTOR", None)

    # Try to add QuickTime to PATH
    quick_time_path = "C:/Program Files (x86)/QuickTime/QTSystem"
    if platform.system() == "windows" and os.path.exists(quick_time_path):
        path_value = env.get("PATH") or ""
        path_paths = [
            path
            for path in path_value.split(os.pathsep)
            if path
        ]
        path_paths.append(quick_time_path)
        env["PATH"] = os.pathsep.join(path_paths)

    # Set default values if are not already set via settings
    defaults = {
        "LOGLEVEL": "DEBUG"
    }
    for key, value in defaults.items():
        if not env.get(key):
            env[key] = value
