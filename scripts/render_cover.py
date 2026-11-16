"""Compose the C cover from a fixed backdrop, native text, and the supplied photo."""

import argparse
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


WIDTH, HEIGHT = 1080, 1920
FRAME = (43, 398, 1037, 1387)
SUBTITLE_POSITION = (153, 203)
SOURCE_TOP = 1214
HEADLINE_BOTTOM = 426
DEFAULT_SOURCE = "特徕福昌岗店"
CREAM = "#fff9e2"
GOLD = "#ffe471"
DARK = "#3d170a"
RESAMPLE = Image.Resampling.LANCZOS
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def get_fonts():
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    headline = fonts / "STXINGKA.TTF"
    source = fonts / "msyhbd.ttc"
    missing = [str(path) for path in (headline, source) if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing C cover fonts: " + ", ".join(missing))
    return headline, source


def fit_font(draw, text, path, max_size, min_size, width, height):
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(path), size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= width and bottom - top <= height:
            return font, (left, top, right, bottom)
    raise ValueError(f"Text exceeds the readable space in the C template: {text}")


def headline_layer(text, path):
    layer = Image.new("RGBA", (904, 163))
    draw = ImageDraw.Draw(layer)
    font, (left, top, right, bottom) = fit_font(draw, text, path, 164, 58, 879, 148)
    x = (layer.width - (right - left)) // 2 - left
    y = (layer.height - (bottom - top)) // 2 - top - 2
    draw.text((x + 3, y + 5), text, font=font, fill="#36190e", stroke_width=2)
    draw.text((x, y), text, font=font, fill=CREAM, stroke_width=1)
    brand_start = text.find("特徕福")
    if brand_start >= 0:
        start = x + draw.textlength(text[:brand_start], font=font)
        draw.text((start, y), "特", font=font, fill=GOLD, stroke_width=1)
    return layer.rotate(5, resample=Image.Resampling.BICUBIC, expand=True)


def brush_layer(width, height, color, highlight):
    layer = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(layer)
    outline = [
        (4, 36), (23, 27), (12, 22), (40, 19), (24, 15), (97, 12),
        (62, 8), (211, 6), (191, 2), (720, 3), (799, 7), (874, 13),
        (849, 16), (887, 22), (867, 25), (895, 34), (880, 39),
        (899, 47), (891, 56), (900, 64), (885, 71), (896, 76),
        (879, 83), (893, 88), (868, 92), (883, 97), (841, 103),
        (858, 107), (754, 110), (777, 114), (415, 113), (282, 117),
        (313, 112), (96, 116), (112, 111), (34, 113), (48, 108),
        (16, 104), (37, 98), (5, 96), (17, 89), (0, 84), (9, 75),
        (2, 70), (10, 62), (2, 56), (14, 49), (4, 45), (21, 40),
    ]
    points = [(round(x * (width - 1) / 900), round(y * (height - 1) / 117))
              for x, y in outline]
    draw.polygon(points, fill=color)
    draw.line((width * .10, height * .24, width * .88, height * .20),
              fill=highlight, width=2)
    draw.line((width * .17, height * .84, width * .81, height * .88),
              fill=highlight, width=2)
    return layer


def composite_with_shadow(target, layer, position, shift=6):
    alpha = Image.new("L", target.size)
    alpha.paste(layer.getchannel("A"), (position[0] + 2, position[1] + shift))
    shadow = Image.new("RGBA", target.size, "#361609")
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(6)).point(lambda value: value // 2))
    target.alpha_composite(shadow)
    target.alpha_composite(layer, position)


def subtitle_layer(text, path):
    banner = brush_layer(882, 142, "#ffe46c", "#fff18f")
    if text:
        draw = ImageDraw.Draw(banner)
        font, (left, top, right, bottom) = fit_font(draw, text, path, 126, 53, 807, 108)
        x = (banner.width - (right - left)) // 2 - left
        y = (banner.height - (bottom - top)) // 2 - top
        draw.text((x, y), text, font=font, fill="#462006", stroke_width=1)
    return banner.rotate(7, resample=Image.Resampling.BICUBIC, expand=True)


def source_layer(shop, path):
    if shop == DEFAULT_SOURCE:
        with Image.open(ASSETS / "approved-source-badge.png") as approved:
            return ImageOps.contain(approved.convert("RGBA"), (895, 145), method=RESAMPLE)
    badge = brush_layer(895, 137, "#fff6d4", "#fff9e8")
    draw = ImageDraw.Draw(badge)
    draw.polygon([(64, 67), (89, 67), (105, 66), (79, 102)], fill="#efad1d")
    draw.ellipse((51, 33, 107, 89), fill="#f7b925")
    draw.ellipse((69, 51, 89, 71), fill="#fff9dd")
    draw.rounded_rectangle((128, 104, 626, 112), radius=4, fill="#efb82e")
    caption = f"素材来源：{shop}"
    font, (_, top, _, bottom) = fit_font(draw, caption, path, 54, 31, 735, 58)
    draw.text((145, (99 - (bottom - top)) // 2 - top + 1), caption, font=font, fill=DARK)
    return badge.rotate(1, resample=Image.Resampling.BICUBIC, expand=True)


def flourish(layer, control, max_width):
    factor = 3
    matte = Image.new("L", (layer.width * factor, 425 * factor))
    draw = ImageDraw.Draw(matte)
    for step in range(151):
        t = step / 150
        a = 1 - t
        weights = (a ** 3, 3 * a * a * t, 3 * a * t * t, t ** 3)
        x, y = (factor * sum(weight * point[axis] for weight, point in zip(weights, control))
                for axis in (0, 1))
        radius = factor * (.2 + max_width * 2 * a * t)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    tint = Image.new("RGBA", (layer.width, 425), CREAM)
    tint.putalpha(matte.resize(tint.size, RESAMPLE))
    layer.alpha_composite(tint)


def extend_photo(inset, size, position):
    """Fill unused space with a continuous extension of the nearest photo edge."""
    canvas = Image.new("RGBA", size)
    x, y = position
    right = x + inset.width
    bottom = y + inset.height
    canvas.paste(inset, position)
    if x:
        left_edge = inset.crop((0, 0, 1, inset.height))
        canvas.paste(left_edge.resize((x, inset.height)), (0, y))
    if right < canvas.width:
        right_edge = inset.crop((inset.width - 1, 0, inset.width, inset.height))
        canvas.paste(right_edge.resize((canvas.width - right, inset.height)), (right, y))
    if y:
        upper_edge = canvas.crop((0, y, canvas.width, y + 1))
        canvas.paste(upper_edge.resize((canvas.width, y)), (0, 0))
    if bottom < canvas.height:
        lower_edge = canvas.crop((0, bottom - 1, canvas.width, bottom))
        canvas.paste(lower_edge.resize((canvas.width, canvas.height - bottom)), (0, bottom))
    return canvas


def place_photo(layer, path, fit, focus, upper_overlay_bottom, source_top):
    x1, y1, x2, y2 = FRAME
    with Image.open(path) as opened:
        photo = ImageOps.exif_transpose(opened).convert("RGBA")
    exposed = (x2 - x1 - 8, y2 - y1 - 8)
    if fit == "cover":
        window = ImageOps.fit(photo, exposed, method=RESAMPLE, centering=focus)
    else:
        photo_top = y1 + 4
        inset_top = max(0, upper_overlay_bottom + 8 - photo_top)
        inset_bottom = source_top - 8 - photo_top
        inset_height = inset_bottom - inset_top
        inset = ImageOps.contain(photo, (exposed[0], inset_height), method=RESAMPLE)
        inset_x = (exposed[0] - inset.width) // 2
        inset_y = inset_top + (inset_height - inset.height) // 2
        window = extend_photo(inset, exposed, (inset_x, inset_y))
    layer.alpha_composite(window, (x1 + 4, y1 + 4))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=CREAM, width=4)
    draw.rectangle((x1 + 14, y1 + 14, x2 - 15, y2 - 15), outline=CREAM, width=3)


def load_headline(path):
    with Image.open(path) as source:
        if source.mode != "RGBA" or source.getchannel("A").getextrema() != (0, 255):
            raise ValueError("headline_image requires a keyed RGBA PNG with transparent background and opaque lettering.")
        artwork = source.crop(source.getbbox())
    return ImageOps.contain(artwork, (1024, HEADLINE_BOTTOM), method=RESAMPLE)


def place_native_headline(group, title, headline_font, banner):
    flourish(group, ((694, 64), (846, -43), (1040, -13), (951, 153)), 8)
    flourish(group, ((143, 232), (-20, 308), (26, 399), (281, 322)), 8)
    draw = ImageDraw.Draw(group)
    draw.polygon([(76, 111), (112, 123), (107, 137), (68, 126)], fill=GOLD)
    draw.polygon([(99, 86), (116, 79), (129, 114), (118, 119)], fill=GOLD)
    if banner:
        composite_with_shadow(group, banner, SUBTITLE_POSITION)
    title_image = headline_layer(title, headline_font)
    composite_with_shadow(group, title_image, (82, 45), shift=2)


def compose(request):
    headline_font, source_font = get_fonts()
    title = request["title"].strip()
    subtitle = request.get("subtitle", "").strip()
    shop = request.get("shop", DEFAULT_SOURCE).strip()
    focus = request.get("focus", [0.5, 0.5])
    fit = request.get("fit", "cover")
    if any("\n" in phrase or "\r" in phrase for phrase in (title, subtitle, shop)):
        raise ValueError("Title, subtitle and store must each be a single line.")
    if not title or not shop:
        raise ValueError("The title and material source store cannot be empty.")
    if fit not in ("cover", "contain") or len(focus) != 2 or not all(0 <= v <= 1 for v in focus):
        raise ValueError("Use fit=cover or contain, and two focus coordinates between 0 and 1.")
    if not title.startswith("【"):
        title = "【" + title
    if subtitle and not subtitle.endswith("】"):
        subtitle += "】"
    if not subtitle and not title.endswith("】"):
        title += "】"

    headline_image = request.get("headline_image")
    artwork = load_headline(headline_image) if headline_image else None
    banner = subtitle_layer(subtitle, headline_font) if subtitle and artwork is None else None
    upper_overlay_bottom = HEADLINE_BOTTOM if artwork else 0
    if banner:
        upper_overlay_bottom = SUBTITLE_POSITION[1] + banner.getbbox()[3]
    badge = source_layer(shop, source_font)
    group = Image.new("RGBA", (WIDTH, FRAME[3]))
    place_photo(group, request["photo"], fit, focus, upper_overlay_bottom, SOURCE_TOP + badge.getbbox()[1])
    if artwork:
        group.alpha_composite(artwork, ((WIDTH - artwork.width) // 2, HEADLINE_BOTTOM - artwork.height))
    else:
        place_native_headline(group, title, headline_font, banner)
    composite_with_shadow(group, badge, ((WIDTH - badge.width) // 2, SOURCE_TOP))
    _, top, _, bottom = group.getbbox()
    return group.crop((0, top, WIDTH, bottom))


def render(request):
    group = compose(request)
    crop_height = request.get("crop_height", 1440)
    if type(crop_height) is not int:
        raise ValueError("Set crop_height in whole pixels.")
    crop_top = request.get("crop_top", (HEIGHT - crop_height) // 2)
    if type(crop_top) is not int or not 0 <= crop_top < crop_top + crop_height <= HEIGHT:
        raise ValueError("Set a crop window within the 1920 px canvas.")
    scale = 1.0
    if crop_height < group.height:
        scale = (crop_height - 8) / group.height
        if scale < .97:
            raise ValueError("This crop needs a larger reduction. Recheck the crop bounds before changing the frame ratio.")
        group = group.resize((round(group.width * scale), crop_height - 8), RESAMPLE)

    ideal_top = (HEIGHT - group.height) // 2
    lower_bound = crop_top + min(16, (crop_height - group.height) // 2)
    upper_bound = crop_top + crop_height - group.height - (lower_bound - crop_top)
    y = min(max(ideal_top, lower_bound), upper_bound)
    with Image.open(ASSETS / "backdrop.png") as image:
        canvas = image.convert("RGBA").resize((WIDTH, HEIGHT), RESAMPLE)
    canvas.alpha_composite(group, ((WIDTH - group.width) // 2, y))
    frame_height = round((FRAME[3] - FRAME[1]) * scale)
    metrics = {
        "frame_height_px": frame_height,
        "frame_percent": round(100 * frame_height / HEIGHT, 2),
        "group_top_px": y,
        "group_bottom_px": HEIGHT - y - group.height,
        "crop_top_px": crop_top,
        "crop_bottom_px": crop_top + crop_height,
        "crop_margin_top_px": y - crop_top,
        "crop_margin_bottom_px": crop_top + crop_height - y - group.height,
    }
    return canvas.convert("RGB"), metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crop-preview", type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    image, metrics = render(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="PNG")
    if args.crop_preview:
        args.crop_preview.parent.mkdir(parents=True, exist_ok=True)
        bounds = (0, metrics["crop_top_px"], WIDTH, metrics["crop_bottom_px"])
        image.crop(bounds).save(args.crop_preview, format="PNG")
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
