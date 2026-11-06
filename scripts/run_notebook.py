r"""Execute a project notebook and save its outputs plus a static HTML preview.

Usage: .\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\02_data_quality.ipynb
"""

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args()
    notebook_path = args.notebook.resolve()
    if notebook_path.parent != ROOT / "notebooks" or notebook_path.suffix != ".ipynb":
        parser.error("Choose an .ipynb file in this project's notebooks folder.")

    # Keep Jupyter's working files inside the project environment.
    for variable, folder in [("JUPYTER_RUNTIME_DIR", "jupyter_runtime"),
                             ("IPYTHONDIR", "ipython"),
                             ("MPLCONFIGDIR", "matplotlib")]:
        target = ROOT / ".venv" / folder
        target.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(target)
    os.environ["JUPYTER_PATH"] = str(ROOT / ".venv" / "share" / "jupyter")
    os.environ.setdefault("MPLBACKEND", "Agg")

    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter

    notebook = nbformat.read(notebook_path, as_version=4)
    nbformat.validate(notebook)
    print(f"Executing {notebook_path.name}...", flush=True)
    client = NotebookClient(
        notebook, timeout=240, kernel_name="ecommerce-analytics",
        resources={"metadata": {"path": str(notebook_path.parent)}},
    )
    client.execute()
    nbformat.validate(notebook)
    nbformat.write(notebook, notebook_path)
    html, _ = HTMLExporter(template_name="lab").from_notebook_node(notebook)
    preview_path = ROOT / "reports" / f"{notebook_path.stem}.html"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(html, encoding="utf-8")
    count = sum(cell.cell_type == "code" for cell in notebook.cells)
    print(f"Saved {count} executed code cells and {preview_path.name}.", flush=True)


if __name__ == "__main__":
    main()
