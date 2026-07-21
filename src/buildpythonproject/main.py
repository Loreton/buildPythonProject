#!/usr/bin/env python3
"""
build.py - Script per costruire bundle e PYZ di lnSync
"""

import os
import shutil
import subprocess
import sys
import tarfile
import argparse
import zipapp
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any

from pyLnLib import PyProjectManager, keyboardPrompt
from pyLnLib.logger import get_logger


def playBeep():
    try:
        soundFile="/usr/share/sounds/freedesktop/stereo/bell.oga"
        if os.path.exists("/usr/bin/paplay") and os.path.exists(soundFile):
            # ctx.logger.info("paplay %s", soundFile)
            subprocess.Popen(["paplay", soundFile])
        else:
            print("\a")
    except Exception as e:
        print("ERROR: Beep failed: %s", e)


class ProjectBuilder:
    def __init__(self, args):
        self.args = args
        self.logger = get_logger()
        # self.project_root = Path(__file__).parent.absolute()
        self.project_root     = Path.cwd() # directory del progetto da lavorare
        self.project_name     = self.project_root.name
        self.target_root_dir  = Path("/home/loreto/filu/Applications/lnAppls") / self.project_name
        self.venv_dir         = self.project_root / ".venv"

        self.pyLnLib_path     = self.project_root.parent / "pyLnLib/src/pyLnLib"
        self.conf_path        = self.project_root / "conf"
        self.dist_dir         = self.target_root_dir / ".dist"
        self.history_dir      = self.target_root_dir / ".history"
        self.history          = args.history



        if not args.test:
            self.bundle_name      = f"{self.project_name}_bundle"
            self.install_dir      = self.target_root_dir / f"{self.project_name}_bundle"
        else:
            self.bundle_name      = f"{self.project_name}_test_bundle"
            self.install_dir      = self.target_root_dir / f"{self.project_name}_test_bundle"

        self.max_history      = 10
        self.target_root_dir.mkdir(parents=True, exist_ok=True)
        self.pyproject_manager = PyProjectManager(self.project_root)
        self.version          = self.pyproject_manager.get_version()


        if self.checkPythonProjectDir():
            self.logger.info("=" * 40)
            self.logger.info("self.project_name     = %s", self.project_name)
            self.logger.info("self.version          = %s", self.version)
            self.logger.info("")
            self.logger.info("self.project_root     = %s", self.project_root)
            self.logger.info("self.pyLnLib_path     = %s", self.pyLnLib_path)
            self.logger.info("self.conf_path        = %s", self.conf_path)
            self.logger.info("")
            self.logger.info("self.target_root_dir  = %s", self.target_root_dir)
            self.logger.info("self.dist_dir         = %s", self.dist_dir)
            self.logger.info("self.bundle_name      = %s", self.bundle_name)
            self.logger.info("self.history_dir      = %s", self.history_dir)
            self.logger.info("")
            self.logger.info("=" * 40)
        else:
            sys.exit(1)


    def checkPythonProjectDir(self) -> bool:
        if not (self.project_root / ".venv").is_dir():
            self.logger.error("ERROR: directory .venv not found!")
            sys.exit(1)

        elif not (self.project_root / "pyproject.toml").is_file():
            self.logger.error("ERROR: file pyproject.toml not found!")
            sys.exit(1)

        return True



    def rotate_previous_build(self, file: Path, file_type: str = "pyz") -> Path:
        """Ruota lo storico dei build"""
        if not self.history_dir:
            self.logger.error("❌ History directory non specificata", exit=True)

        self.history_dir.mkdir(parents=True, exist_ok=True)

        if not file.exists():
            self.logger.error("file: %s nonsiste", file, exit=True)

        self.logger.info("Rotating %s build history",file_type)
        if file_type=='pyz':
            file_type='bin'

        # Usa l'estensione corretta
        extension = file.suffix
        prefix = f"{self.project_name}_{file_type}_{self.version}_v"

        # Ruota dalla versione più vecchia alla più nuova
        for i in range(self.max_history, 1, -1):
            src = self.history_dir / f"{prefix}{i-1:02d}{extension}"
            dst = self.history_dir / f"{prefix}{i:02d}{extension}"
            if src.exists():
                # self.logger.info(f"moving version {prefix}{i-1:02d}{extension} to {prefix}{i:02d}{extension}")
                self.logger.debug("moving version:\nfrom: %s\nto: %s", src, dst)
                src.replace(dst)

        # Salva la versione più recente
        latest = self.history_dir / f"{prefix}01{extension}"
        # shutil.copy2(file, latest) # evitiamo di rimuoverlo da dist
        file.replace(latest)  # lo rimuove anche da dist
        self.logger.info("✅ Saved previous build as:\n%s", latest)
        return latest




    def clean_doc(self, text: Any, *args) -> str:
        import inspect
        # Se il msg contiene placeholder come %s, sostituiscili
        if args:
            formatted_msg = text % args
            args=() # azzera args
        else:
            formatted_msg = text
        """Wrapper per inspect.cleandoc con type ignore."""
        return inspect.cleandoc(formatted_msg)  # type: ignore



    #######################################################################
    # inspect.cleandoc():
    #    Gestisce correttamente shebang (#!/usr/bin/env python3)
    #    Mantiene la formattazione leggibile nel codice Python
    #    Rimuove solo l'indentazione comune minima
    #    Non richiede backslash o trucchi strani
    # 4. Crea __main__.py
    #######################################################################
    def create_main_py(self, filename: Path, filemode: int=0o444):
        # import inspect
        content = self.clean_doc(f'''
            #!/usr/bin/env python3
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).parent))

            from {self.project_name.lower()}.main import main

            if __name__ == "__main__":
                sys.exit(main())
        ''')

        # 4. Crea script di avvio
        self.logger.info("• Creazione __main__.py")
        filename.write_text(content)
        if filemode != 0:
            filename.chmod(filemode) # filename.chmod(0o755)



    #######################################################################
    # textwrap.dedent():
    #    Gestisce correttamente shebang (#!/usr/bin/env python3)
    #    Mantiene la formattazione leggibile nel codice Python
    #    Rimuove solo l'indentazione comune minima
    #    richiede backslash sulla prima riga
    # 4. Crea __main__.py
    #######################################################################
    def create_main_py_wrapper(self, filename: Path, filemode: int=0o444):
        import textwrap
        content =  textwrap.dedent(f'''\
            #!/usr/bin/env python3
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
    def create_run_sh(self, filename: Path, name: str, filemode: int=0o444):
        content = self.clean_doc(f'''
                #!/bin/bash
                # {self.project_name} v{self.version} - Portable Bundle

                scriptFullPath="$(readlink -f ${{BASH_SOURCE[0]}})"       # OTTIMA
                SCRIPT_DIR="$(dirname $scriptFullPath)"
                source "$SCRIPT_DIR/.venv/bin/activate"
                python "$SCRIPT_DIR/{name}" "$@"
            ''')


        # 4. Crea script di avvio
        self.logger.info("• Creating run.sh...")
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
    def create_readme(self, filename: Path, name: str, filemode: int=0o444):
        content = self.clean_doc(f'''
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
        self.logger.info("• Creating README.md...")
        filename.write_text(content)
        if filemode != 0:
            filename.chmod(filemode) # filename.chmod(0o755)



    def create_pyz(self) -> Path:
        """Crea un PYZ eseguibile con struttura piatta"""
        self.logger.info("• Creating PYZ executable...")

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            self.logger.info("• create_pyz temp dir:\n%s", temp_dir)

            # 1. Copia pyLnLib
            if self.pyLnLib_path.exists():
                self.logger.info("• Copiando pyLnLib da: %s", self.pyLnLib_path)
                shutil.copytree(self.pyLnLib_path, temp_dir / "pyLnLib",
                              ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.git'))

            # 2. Copia source
            my_source = self.project_root / "src" / self.project_name.lower()
            if my_source.exists():
                self.logger.info("• Copying source from: %s", my_source)
                shutil.copytree(my_source, temp_dir / self.project_name.lower(), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

            # 3. Copia conf

            if self.conf_path.exists():
                self.logger.info("• Copying conf from: %s", self.conf_path)
                shutil.copytree(self.conf_path, temp_dir / "conf", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

            # 4. Crea __main__.py
            self.create_main_py(filename=temp_dir / "__main__.py")

            # 5. Crea il PYZ
            pyz_path = self.dist_dir / f"{self.project_name}_{self.version}.pyz"
            zipapp.create_archive(str(temp_dir), target=str(pyz_path), interpreter="/usr/bin/env python3")
            pyz_path.chmod(0o755)

            self.logger.info("✅ PYZ creato: %s", pyz_path)
            _size = pyz_path.stat().st_size / (1024 * 1024)
            self.logger.info("📊 Dimensione: %s", f"{_size:.2f} MB")

            # Test rapido
            self.logger.info("• Testing...")
            result = subprocess.run([sys.executable, str(pyz_path), "--help"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info("✅ run test is OK!")
            else:
                self.logger.info("⚠️ run test failed: %s", result.stderr[:200])
                self.logger.info("⚠️ run test failed: %s", result.stderr)


            return pyz_path

    def create_bundle(self):
        """Crea il bundle portabile (PYZ + venv)"""
        self.logger.info("🎒 Creazione bundle portabile...")

        # Prima crea il PYZ
        pyz_path = self.create_pyz()

        # Crea directory temporanea per il bundle
        temp_dir = self.project_root / f"temp_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(exist_ok=True)
        self.create_bundle_temp_dir = temp_dir # mi serve per copiarce dentro la conf/ dir
        self.logger.info("• create_bundle temp dir: %s", temp_dir)

        try:
            # 1. Copia il PYZ
            self.logger.info("• Copiando PYZ nel bundle...")
            shutil.copy2(pyz_path, temp_dir / pyz_path.name)

            self.logger.info("• Creando virtual environment...")
            venv_bundle_dir = temp_dir / ".venv"

            CREATE_VENV: bool = False
            if CREATE_VENV:
                # 2. Crea virtual environment installando i package presenti in pyproject.toml
                subprocess.run([sys.executable, "-m", "venv", str(venv_bundle_dir)], check=True)

                # 3. Installa le dipendenze base (lette dal file pyproject.toml) ma in teoria dovrebbero già essere in .venv
                self.logger.info("• Installando dipendenze base...")
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
                    self.logger.info(f"   • Installando: {', '.join(dependencies[:3])}{'...' if len(dependencies) > 3 else ''}")
                    # self.logger.info("• Installando: {', '.join(dependencies[:3])}{'...' if len(dependencies) > 3 else ''}")
                    subprocess.run([str(pip), "install", *dependencies], check=False)
                else:
                    self.logger.info("• Nessuna dipendenza esterna da installare")

            else:
                # Copy existing venv to bundle (preserve symlinks)
                self.logger.info("• Copying venv to %s...", venv_bundle_dir)
                shutil.copytree(self.venv_dir, venv_bundle_dir, symlinks=True ) # Preserve symlinks

            # copy conf/ dir  per averla anchesterna la .pyz
            if self.conf_path.exists():
                # self.logger.info(f"   • Copying conf from: {self.conf_path}")
                self.logger.info("• Copying %s into bundle but outside .pyz", self.conf_path)
                shutil.copytree(self.conf_path, temp_dir / "conf", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


            # 4. Crea script di avvio
            self.create_run_sh(filename=temp_dir / "run.sh", name=pyz_path.name, filemode=0o755)
            self.create_readme(filename=temp_dir / "README.txt", name=pyz_path.name, filemode=0)

            # 6. Crea il tarball (questa parte mancava!)
            self.logger.info("• Creando archive tar.gz...")
            # bundle_name = f"{self.project_name}_{self.version}_bundle.tgz"
            bundle_name = f"{self.bundle_name}_{self.version}.tgz"
            bundle_path = self.dist_dir / bundle_name

            with tarfile.open(bundle_path, "w:gz") as tar:
                # tar.add(temp_dir, arcname=f"{self.project_name}_bundle")
                tar.add(temp_dir, arcname=f"{self.bundle_name}")

            self.logger.info("✅ Bundle creato: %s", bundle_path)
            _size = bundle_path.stat().st_size / (1024 * 1024)
            self.logger.info("📊 Dimensione: %s", f"{_size:.2f} MB")

            # self.logger.info("📁 Struttura del bundle:")
            # self.logger.info("   %s/", self.bundle_name)
            # self.logger.info("   ├── %s", pyz_path.name)
            # self.logger.info("   ├── .venv/")
            # self.logger.info("   ├── run.sh")
            # self.logger.info("   ├── run.bat")
            # self.logger.info("   └── README.txt")
            self.logger.info(self.clean_doc("""
                📁 Struttura del bundle:
                    %s/
                    ├── %s
                    ├── .venv/
                    ├── run.sh
                    ├── run.bat
                    └── README.txt""", self.bundle_name, pyz_path.name))

        except Exception as e:
            self.logger.info("❌ Errore durante la creazione del bundle: %s", e)
            raise

        finally:
            # Pulisci directory temporanea
            self.logger.info("• Pulendo directory temporanea...")
            shutil.rmtree(temp_dir, ignore_errors=True)

        return bundle_path


    def clean(self):
        """Pulisci dist dir"""
        self.logger.info("🧹 Pulendo...")
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir()
        self.logger.info("✅ Pulito!")

    def run(self):
        choice = keyboardPrompt("press '--go' to continue, any ENTER to exit: ", validKeys=['--go'], exitKeys=['ENTER', 'q'])
        if not choice[0] == '--go':
            self.logger.info("Exiting on user request.")
            sys.exit(0)


        self.dist_dir.mkdir(exist_ok=True)

        if self.args.clean:
            self.clean()

        elif self.args.build:
            pyz_path = self.create_pyz()
            if self.history_dir:
                latest               = self.rotate_previous_build(pyz_path, "pyz") # latest è Path | None
                latest_relative_path = latest.relative_to(self.target_root_dir) # type: ignore
                link_name            = self.target_root_dir / f"{self.project_name}_lnk.pyz"
                self.logger.info("• Creating link:\nsrc: %s\nlnk: %s", link_name, latest_relative_path)
                subprocess.run(["ln", "-sfn", latest_relative_path, link_name ])

        elif self.args.bundle:
            bundle_path = self.create_bundle()

            if self.history_dir:
                if not self.args.test:
                    latest               = self.rotate_previous_build(bundle_path, "bundle") # latest è Path | None
                    link_name            = self.target_root_dir / f"{self.project_name}_lnk.tgz"
                    latest_relative_path = latest.relative_to(self.target_root_dir) # type: ignore
                    self.logger.info("• Creating link:\nsrc: %s\nlnk: %s", link_name, latest_relative_path)
                    subprocess.run(["ln", "-sfn", latest_relative_path, link_name ])
                    bundle_path = latest

            if self.args.install: ### unpack bundle_path in bundle dir
                self.logger.info("removing %s", self.install_dir)
                if self.install_dir.exists():
                    shutil.rmtree(self.install_dir)

                prev_cwd = Path.cwd()
                # import pdb; pdb.set_trace();  # by Loreto
                os.chdir(self.target_root_dir)
                subprocess.run(["tar", "-xf", bundle_path ])
                os.chdir(prev_cwd)
                self.logger.info("Installed\nbundle: %s\ninto: %s", bundle_path, self.install_dir)
                self.logger.info("command to test:\npython %s/run.sh", self.install_dir)

        else:
            self.logger.info("❌ Enter a vaild option!")
            sys.exit(1)

        self.logger.info("✨ Build completata!")

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
