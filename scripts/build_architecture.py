"""Embed the documentation SVGs and render the optional HTML walkthrough."""
import argparse
import base64
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', type=Path, required=True,
                        help="Path to visual-explainer's kit/render.mjs")
    args = parser.parse_args()
    renderer = args.renderer.resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    docs = root / 'docs'
    source = (docs / 'architecture.src.html').read_text(encoding='utf-8')

    def embed(match):
        asset = (docs / match.group(1)).resolve(strict=True)
        if asset.parent != docs or asset.suffix != '.svg':
            raise ValueError('Only SVG files in docs/ may be embedded')
        encoded = base64.b64encode(asset.read_bytes()).decode('ascii')
        return f'src="data:image/svg+xml;base64,{encoded}"'

    source = re.sub(r'src="([^":]+\.svg)"', embed, source)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.src.html', prefix='.architecture-',
                                     dir=docs, encoding='utf-8', newline='\n', delete=False) as f:
        f.write(source)
        prepared = Path(f.name)
    try:
        subprocess.run(['node', str(renderer), str(prepared), '-o', str(docs / 'architecture.html'),
                        '--root', str(root)], check=True)
    finally:
        prepared.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
