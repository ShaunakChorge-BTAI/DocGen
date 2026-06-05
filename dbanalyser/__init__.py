import sys
from pathlib import Path
workspace_root = str(Path(__file__).parent.parent.resolve())
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

__version__ = "1.0.0"
__app_name__ = "DBAnalyser"
