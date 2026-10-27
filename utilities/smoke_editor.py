"""Load and paint the existing sample project, then exit without saving."""
import os
from pathlib import Path
import sys
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main():
    from app.editor.editor_locale import init_locale
    init_locale()
    from app.engine.codegen import source_generator
    source_generator.generate_all()
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import QTimer
    import pygame
    pygame.font.init()
    app = QApplication([])
    from app import dark_theme
    dark_theme.set(app, dark_theme.get_theme())
    from app.editor.main_editor import MainEditor
    from app.editor.settings import MainSettingsController

    def migration_only(parent, title, message, *args, **kwargs):
        if 'Apply updates?' in message:
            print('Migrating temporary sample copy:', message, flush=True)
            return QMessageBox.Ok
        raise RuntimeError('Unexpected editor warning: ' + message)

    # A disposable copy also protects against autosave and migration writes.
    # testing_proj is an old fixture with a missing portrait; use the supported
    # default sample for the editor's normal load path.
    with TemporaryDirectory(prefix='lt-editor-smoke-') as folder:
        project = str(Path(folder) / 'sample.ltproj')
        shutil.copytree(ROOT / 'default.ltproj', project)
        with patch.object(QMessageBox, 'warning', side_effect=migration_only), \
                patch.object(MainSettingsController, 'get_current_project', return_value=project), \
                patch.object(MainSettingsController, 'set_current_project'), \
                patch.object(MainSettingsController, 'append_or_bump_project'):
            window = MainEditor(project)
            window.show()
            QTimer.singleShot(1500, app.quit)
            app.exec_()
            print('EDITOR_SMOKE_OK:', window.windowTitle(), flush=True)
            window.hide()


if __name__ == '__main__':
    main()
