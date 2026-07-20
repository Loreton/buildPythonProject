#!/usr/bin/env python3
"""
build.py - Script per costruire bundle e PYZ di lnSync
"""

import os
import shutil
import subprocess
import sys
import tarfile
import json
import argparse
from turtle import pd
import zipapp
import tempfile
from pathlib import Path
from datetime import datetime

def playBeep():
    try:
        soundFile="/usr/share/sounds/freedesktop/stereo/bell.oga"
        if os.path.exists("/usr/bin/paplay") and os.path.exists(soundFile):
            # ctx.logger.info("paplay %s", soundFile)
            subprocess.Popen(["paplay", soundFile])
        else:
            print("\a")
    except Exception as e:
        print("Beep failed:", e)


class ProjectBuilder:
    def __init__(self, args):
        self.args = args
        # self.project_root = Path(__file__).parent.absolute()
        self.project_root     = Path.cwd()
        self.project_name     = self.project_root.name
        self.target_root_dir  = Path("/home/loreto/filu/Applications/lnAppls") / self.project_name
        self.venv_dir         = self.project_root / ".venv"

        self.pyLnLib_path     = self.project_root.parent / "pyLnLib/src/pyLnLib"
        self.conf_path        = self.project_root / "conf"
        self.version          = self.get_version()
        self.dist_dir         = self.target_root_dir / ".dist"
        self.history_dir      = self.target_root_dir / ".history" if args.history else None

        if not args.test:
            self.bundle_name      = f"{self.project_name}_bundle"
            self.install_dir      = self.target_root_dir / self.project_name / "_bundle"
        else:
            self.bundle_name      = f"{self.project_name}_test_bundle"
            self.install_dir      = self.target_root_dir / self.project_name / "_test_bundle"


        self.max_history      = 10

        self.target_root_dir.mkdir(parents=True, exist_ok=True)

        if self.checkPythonProjectDir():
            print("=" * 40)
            print(f"\t{str(self.project_name)     = }")
            print(f"\t{str(self.version)          = }")
            print()
            print(f"\t{str(self.project_root)     = }")
            print(f"\t{str(self.pyLnLib_path)     = }")
            print(f"\t{str(self.conf_path)        = }")
            print()
            print(f"\t{str(self.target_root_dir)  = }")
            print(f"\t{str(self.dist_dir)         = }")
            print(f"\t{str(self.bundle_name)      = }")
            print(f"\t{str(self.history_dir)      = }")
            print()
            print("=" * 40)
        else:
            sys.exit(1)


    def checkPythonProjectDir(self) -> str:
        if not (self.project_root / ".venv").is_dir():
            print("ERROR: directory .venv not found!")
            return False

        elif not (self.project_root / "pyproject.toml").is_file():
            print("ERROR: file pyproject.toml not found!")
            return False

        elif not (self.project_root / "library.json").is_file(): # solo per progetti non python
            print("ERROR: file library.json not found!")
            return True

        return True



    def rotate_previous_build(self, file: Path, file_type: str = "pyz") -> str:
        """Ruota lo storico dei build"""
        if not self.history_dir:
            print("❌ History directory non specificata")
            return

        self.history_dir.mkdir(parents=True, exist_ok=True)

        if not file.exists():
            return

        print(f"🔄 Rotating {file_type} build history")
        if file_type=='pyz': file_type='bin'

        # Usa l'estensione corretta
        extension = file.suffix
        prefix = f"{self.project_name}_{file_type}_{self.version}_v"

        # Ruota dalla versione più vecchia alla più nuova
        for i in range(self.max_history, 1, -1):
            src = self.history_dir / f"{prefix}{i-1:02d}{extension}"
            dst = self.history_dir / f"{prefix}{i:02d}{extension}"
            if src.exists():
                print(f"moving version {prefix}{i-1:02d}{extension} to {prefix}{i:02d}{extension}")
                src.replace(dst)

        # Salva la versione più recente
        latest = self.history_dir / f"{prefix}01{extension}"
        # shutil.copy2(file, latest) # evitiamo di rimuoverlo da dist
        file.replace(latest)  # lo rimuove anche da dist
        print(f"✅ Saved previous build as: {latest}")
        return latest



    def get_version(self) -> str:
        """Recupera la versione da library.json"""
        library_json = self.project_root / "library.json"
        if library_json.exists():
            try:
                with open(library_json) as f:
                    data = json.load(f)
                    if "version" in data:
                        return data["version"]
            except:
                pass
        return datetime.now().strftime("%Y%m%d_%H%M%S")





    #######################################################################
    # inspect.cleandoc():
    #    Gestisce correttamente shebang (#!/usr/bin/env python3)
    #    Mantiene la formattazione leggibile nel codice Python
    #    Rimuove solo l'indentazione comune minima
    #    Non richiede backslash o trucchi strani
    # 4. Crea __main__.py
    #######################################################################
    def create_main_py(self, filename: str, filemode: oct=0o444):
        import inspect
        content =  inspect.cleandoc(f'''#!/usr/bin/env python3
                    import sys
                    from pathlib import Path

                    sys.path.insert(0, str(Path(__file__).parent))

                    from {self.project_name.lower()}.main import main

                    if __name__ == "__main__":
                        sys.exit(main())
                ''')

        # 4. Crea script di avvio
        print("   • Creazione __main__.py")
        filename.write_text(content)
        if filemode != 0:
            filename.chmod(filemode) # filename.chmod(0o755)


    #######################################################################
    # inspect.cleandoc():
    #    Gestisce correttamente shebang (#!/usr/bin/env python3)
    #    Mantiene la formattazione leggibile nel codice Python
    #    Rimuove solo l'indentazione comune minima
    #    Non richiede backslash o trucchi strani
    # 4. Crea run.sh
    #######################################################################
    def create_run_sh(self, filename: str, name: str, filemode: oct=0o444):
        import inspect
        content =  inspect.cleandoc(f'''#!/bin/bash
                # {self.project_name} v{self.version} - Portable Bundle

                    scriptFullPath="$(readlink -f ${{BASH_SOURCE[0]}})"       # OTTIMA
                    SCRIPT_DIR="$(dirname $scriptFullPath)"
                    source "$SCRIPT_DIR/.venv/bin/activate"
                    python "$SCRIPT_DIR/{name}" "$@"
            ''')


        # 4. Crea script di avvio
        print("   • Creating run.bat...")
        filename.write_text(content)
        if filemode != 0:
            filename.chmod(filemode) # filename.chmod(0o755)




    #######################################################################
    # inspect.cleandoc():
    #    Gestisce correttamente shebang (#!/usr/bin/env python3)
    #    Mantiene la formattazione leggibile nel codice Python
    #    Rimuove solo l'indentazione comune minima
    #    Non richiede backslash o trucchi strani
    # 4. Crea run.bat
    #######################################################################
    def create_readme(self, filename: str, name: str, filemode: oct=0o444):
        import inspect

        content = inspect.cleandoc(f'''
                # {self.project_name} v{self.version} - Portable Bundle

                ## Utilizzo
                    Linux/macOS: ./run.sh --help
                    Windows: run.bat --help

                ## Contenuto
                    - {name}: Applicazione principale
                    - .venv/: Python environment con dipendenze
                    - run.sh/run.bat: Script di avvio
                ''')


        # 4. Crea script di avvio
        print("   • Creating README.md...")
        filename.write_text(content)
        if filemode != 0:
            filename.chmod(filemode) # filename.chmod(0o755)



    def create_pyz(self) -> str:
        """Crea un PYZ eseguibile con struttura piatta"""
        print("\n📦 Creazione PYZ eseguibile...")

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            print(f"   • create_pyz temp dir: {temp_dir}")

            # 1. Copia pyLnLib
            if self.pyLnLib_path.exists():
                print(f"   • Copiando pyLnLib da: {self.pyLnLib_path}")
                shutil.copytree(self.pyLnLib_path, temp_dir / "pyLnLib",
                              ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.git'))

            # 2. Copia source
            my_source = self.project_root / "src" / self.project_name.lower()
            if my_source.exists():
                print(f"   • Copying source from: {my_source}")
                shutil.copytree(my_source, temp_dir / self.project_name.lower(), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

            # 3. Copia conf

            if self.conf_path.exists():
                # print(f"   • Copying conf from: {self.conf_path}")
                print(f"   • Copying {self.conf_path} inside pyz")
                shutil.copytree(self.conf_path, temp_dir / "conf", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

            # 4. Crea __main__.py
            self.create_main_py(filename=temp_dir / "__main__.py")

            # 5. Crea il PYZ
            pyz_path = self.dist_dir / f"{self.project_name}_{self.version}.pyz"
            zipapp.create_archive(str(temp_dir), target=str(pyz_path), interpreter="/usr/bin/env python3")
            pyz_path.chmod(0o755)

            print(f"✅ PYZ creato: {pyz_path}")
            print(f"📊 Dimensione: {pyz_path.stat().st_size / (1024 * 1024):.2f} MB")

            # Test rapido
            print("   • Testing...")
            result = subprocess.run([sys.executable, str(pyz_path), "--help"], capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✅ run test is OK!")
            else:
                print(f"   ⚠️ run test failed: {result.stderr[:200]}")
                print(f"   ⚠️ run test failed: {result.stderr}")


            return pyz_path

    def create_bundle(self):
        """Crea il bundle portabile (PYZ + venv)"""
        print("\n🎒 Creazione bundle portabile...")

        # Prima crea il PYZ
        pyz_path = self.create_pyz()

        # Crea directory temporanea per il bundle
        temp_dir = self.project_root / f"temp_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(exist_ok=True)
        self.create_bundle_temp_dir = temp_dir # mi serve per copiarce dentro la conf/ dir
        print(f"   • create_bundle temp dir: {temp_dir}")

        try:
            # 1. Copia il PYZ
            print("   • Copiando PYZ nel bundle...")
            shutil.copy2(pyz_path, temp_dir / pyz_path.name)

            print("   • Creando virtual environment...")
            venv_bundle_dir = temp_dir / ".venv"

            CREATE_VENV: bool = False
            if CREATE_VENV:
                # 2. Crea virtual environment installando i package presenti in pyproject.toml
                subprocess.run([sys.executable, "-m", "venv", str(venv_bundle_dir)], check=True)

                # 3. Installa le dipendenze base (lette dal file pyproject.toml) ma in teoria dovrebbero già essere in .venv
                print("   • Installando dipendenze base...")
                pip = venv_bundle_dir / "bin" / "pip"

                dependencies = []
                pyproject = self.project_root / "pyproject.toml"
                if pyproject.exists():
                    try:
                        import tomllib
                        with open(pyproject, "rb") as f:
                            data = tomllib.load(f)
                            if "project" in data and "dependencies" in data["project"]:
                                for dep in data["project"]["dependencies"]:
                                    if not any(x in dep for x in ['pyLnLib', '-e', '../', './', 'editable']):
                                        dependencies.append(dep)
                    except:
                        pass

                if dependencies:
                    print(f"   • Installando: {', '.join(dependencies[:3])}{'...' if len(dependencies) > 3 else ''}")
                    subprocess.run([str(pip), "install", *dependencies], check=False)
                else:
                    print("   • Nessuna dipendenza esterna da installare")

            else:
                # Copy existing venv to bundle (preserve symlinks)
                print(f"   Copying venv to {venv_bundle_dir = }...")
                shutil.copytree(self.venv_dir, venv_bundle_dir, symlinks=True ) # Preserve symlinks

            # copy conf/ dir  per averla anchesterna la .pyz
            if self.conf_path.exists():
                # print(f"   • Copying conf from: {self.conf_path}")
                print(f"   • Copying {self.conf_path} into bundle but outside .pyz")
                shutil.copytree(self.conf_path, temp_dir / "conf", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


            # 4. Crea script di avvio
            self.create_run_sh(filename=temp_dir / "run.sh", name=pyz_path.name, filemode=0o755)
            self.create_readme(filename=temp_dir / "README.txt", name=pyz_path.name, filemode=0)

            # 6. Crea il tarball (questa parte mancava!)
            print("   • Creando archive tar.gz...")
            # bundle_name = f"{self.project_name}_{self.version}_bundle.tgz"
            bundle_name = f"{self.bundle_name}_{self.version}.tgz"
            bundle_path = self.dist_dir / bundle_name

            with tarfile.open(bundle_path, "w:gz") as tar:
                # tar.add(temp_dir, arcname=f"{self.project_name}_bundle")
                tar.add(temp_dir, arcname=f"{self.bundle_name}")

            print(f"✅ Bundle creato: {bundle_path}")
            print(f"📊 Dimensione: {bundle_path.stat().st_size / (1024 * 1024):.2f} MB")

            print("\n📁 Struttura del bundle:")
            print(f"   {self.bundle_name}/")
            print(f"   ├── {pyz_path.name}")
            print( "   ├── .venv/")
            print( "   ├── run.sh")
            print( "   ├── run.bat")
            print( "   └── README.txt")

        except Exception as e:
            print(f"   ❌ Errore durante la creazione del bundle: {e}")
            raise

        finally:
            # Pulisci directory temporanea
            print("   • Pulendo directory temporanea...")
            shutil.rmtree(temp_dir, ignore_errors=True)

        return bundle_path


    def clean(self):
        """Pulisci dist dir"""
        print("🧹 Pulendo...")
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir()
        print("✅ Pulito!")

    def run(self):

        choice=input("press 'c' to continue, any key to exit: ").lower()
        if not choice == 'c':
            print("Exiting on user request.")
            sys.exit(0)


        self.dist_dir.mkdir(exist_ok=True)

        if self.args.clean:
            self.clean()

        elif self.args.build:
            pyz_path = self.create_pyz()
            if self.history_dir:
                latest               = self.rotate_previous_build(pyz_path, "pyz")
                latest_relative_path = latest.relative_to(self.target_root_dir)
                link_name            = self.target_root_dir / f"{self.project_name}_lnk.pyz"
                print(f"   • Creating {link_name} --> {latest_relative_path}")
                subprocess.run(["ln", "-sfn", latest_relative_path, link_name ])

        elif self.args.bundle:
            bundle_path = self.create_bundle()

            if self.history_dir:
                if not self.args.test:
                    latest               = self.rotate_previous_build(bundle_path, "bundle")
                    link_name            = self.target_root_dir / f"{self.project_name}_lnk.tgz"
                    latest_relative_path = latest.relative_to(self.target_root_dir)
                    print(f"   • Creating {link_name} --> {latest_relative_path}")
                    subprocess.run(["ln", "-sfn", latest_relative_path, link_name ])


            if self.args.install: ### unpack bundle_path in bundle dir
                print(f"removing {self.install_dir}")
                if self.install_dir.exists():
                    shutil.rmtree(self.install_dir)

                prev_cwd = Path.cwd()
                os.chdir(self.target_root_dir)
                subprocess.run(["tar", "-xf", bundle_path ])
                os.chdir(prev_cwd)

        else:
            print("\n❌ Enter a vaild option!")
            sys.exit(1)

        print("\n✨ Build completata!")

def main():
    if len(sys.argv) == 1:
       sys.argv.append("-h")
    parser = argparse.ArgumentParser(description="Build Tool for python project")
    parser.add_argument("--history", action="store_true", help="create history of packages")
    parser.add_argument("--install", action="store_true", help="install bundle.tgz package to unpack_dir")
    parser.add_argument("--test", action="store_true", help="install bundle.tgz package to temporary unpack_dir")


    group=parser.add_argument_group('--------- action options')
    action=group.add_mutually_exclusive_group(required=True)

    action.add_argument("--build", action="store_true", help="Build PYZ")
    action.add_argument("--bundle", action="store_true", help="Build PYZ and bundle")
    action.add_argument("--clean", action="store_true", help="Clean dist area")


    # parser.add_argument("--build", action="store_true", help="Build solo PYZ")
    # parser.add_argument("--bundle", action="store_true", help="Build solo bundle")
    # parser.add_argument("--clean", action="store_true", help="Pulisci")
    args = parser.parse_args()



    ProjectBuilder(args).run()
    playBeep()

if __name__ == "__main__":
    main()
