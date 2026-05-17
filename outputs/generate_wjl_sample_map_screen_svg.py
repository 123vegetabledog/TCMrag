import base64
from pathlib import Path


def main():
    png_path = Path("/workspace/outputs/china-map-10provinces.png")
    out_path = Path("/workspace/outputs/wjl-sample-map-screen-1920x1080.svg")

    png_b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    png_data_uri = f"data:image/png;base64,{png_b64}"

    width = 1920
    height = 1080

    title_main = "王金良团队 10 万+ 青少年样本分布"
    title_sub = "（10 省市）"
    coverage_line = "覆盖：重庆、四川、云南、贵州、湖北、湖南、广东、河南、山东、浙江"

    map_x = 80
    map_y = 190
    map_w = 1760
    map_h = 790
    map_r = 24

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <clipPath id="mapClip">
      <rect x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}" rx="{map_r}" ry="{map_r}" />
    </clipPath>
  </defs>

  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF" />

  <text x="80" y="92" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="54" font-weight="700" fill="#0B1F33">{title_main}</text>
  <text x="80" y="140" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="28" font-weight="500" fill="#3D556E">{title_sub}</text>
  <text x="80" y="172" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="20" font-weight="400" fill="#58738F">{coverage_line}</text>

  <rect x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}" rx="{map_r}" ry="{map_r}" fill="#FFFFFF" stroke="#E6EAF0" stroke-width="2" />
  <image x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}" href="{png_data_uri}" clip-path="url(#mapClip)" preserveAspectRatio="xMidYMid meet" />

  <g>
    <rect x="80" y="1012" width="18" height="18" rx="4" ry="4" fill="#FF4D4F" />
    <text x="106" y="1027" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="18" font-weight="500" fill="#22364A">重庆</text>

    <rect x="170" y="1012" width="18" height="18" rx="4" ry="4" fill="#FA8C16" />
    <text x="196" y="1027" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="18" font-weight="500" fill="#22364A">覆盖省市</text>

    <rect x="284" y="1012" width="18" height="18" rx="4" ry="4" fill="#E8EDF2" stroke="#CBD5E1" stroke-width="1" />
    <text x="310" y="1027" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="18" font-weight="500" fill="#22364A">其他省份</text>

    <text x="80" y="1060" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="16" font-weight="400" fill="#6B7F93">说明：高亮为样本覆盖省市；底图为标准行政区底图（示意）。</text>
  </g>

  <g>
    <rect x="1590" y="1006" width="250" height="62" rx="12" ry="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="2" />
    <text x="1715" y="1045" text-anchor="middle" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="20" font-weight="600" fill="#6B7F93">LOGO</text>
    <text x="1840" y="1068" text-anchor="end" font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="14" font-weight="400" fill="#6B7F93">来源：王金良团队长期调研地（示意）</text>
  </g>
</svg>
"""

    out_path.write_text(svg, encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()

