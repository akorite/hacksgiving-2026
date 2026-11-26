from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import ForensicBundle, VerdictType

COLORS = {VerdictType.VERIFIED: "#38a169", VerdictType.SUSPICIOUS: "#d69e2e", VerdictType.MALICIOUS: "#e53e3e", VerdictType.INCONCLUSIVE: "#718096"}


def annotate_xray(bundle: ForensicBundle, verdict: VerdictType, output: Path) -> Path:
    if not bundle.rendered_pages:
        img = Image.new("RGB", (900, 600), "#101820")
    else:
        img = Image.open(bundle.rendered_pages[0].png_path).convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    color = COLORS[verdict]
    draw.rectangle((0, 0, img.width - 1, img.height - 1), outline=color, width=12)
    for region in bundle.diff_regions:
        if region.page == 1:
            draw.rectangle((region.x, region.y, region.x + region.width, region.y + region.height), outline="#ff00ff", width=5)
    label = f"{verdict.value} • Cupbearer X-Ray"
    draw.rectangle((0, 0, img.width, 42), fill="#101820")
    draw.text((16, 10), label, fill=color, font=ImageFont.load_default())
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)
    return output
