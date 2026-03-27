/**
 * 基于种子字符串生成像素风格头像
 * 生成一个 5x5 的对称像素图案，类似 GitHub identicon
 */

// 预设的颜色方案（柔和的颜色，适合做头像背景）
const AVATAR_COLORS = [
  "#E57373", // 红
  "#F06292", // 粉
  "#BA68C8", // 紫
  "#9575CD", // 深紫
  "#7986CB", // 靛蓝
  "#64B5F6", // 蓝
  "#4FC3F7", // 浅蓝
  "#4DD0E1", // 青
  "#4DB6AC", // 蓝绿
  "#81C784", // 绿
  "#AED581", // 浅绿
  "#DCE775", // 黄绿
  "#FFD54F", // 琥珀
  "#FFB74D", // 橙
  "#FF8A65", // 深橙
  "#A1887F", // 棕
];

/**
 * 简单的字符串哈希函数
 */
function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

/**
 * 基于种子生成伪随机数
 */
function seededRandom(seed: number, index: number): number {
  const x = Math.sin(seed + index) * 10000;
  return x - Math.floor(x);
}

/**
 * 生成像素头像的 SVG 字符串
 * @param seed - 种子字符串（通常是用户 ID 或邮箱）
 * @param size - SVG 尺寸（默认 80）
 * @returns SVG 字符串
 */
export function generatePixelAvatar(seed: string, size: number = 80): string {
  const hash = hashCode(seed);

  // 选择主色调
  const colorIndex = hash % AVATAR_COLORS.length;
  const mainColor = AVATAR_COLORS[colorIndex];

  // 生成 5x5 像素图案（左半边生成，右半边镜像）
  // 实际只需要生成 3 列（0, 1, 2），列 3 和 4 是镜像
  const pixels: boolean[][] = [];
  for (let row = 0; row < 5; row++) {
    pixels[row] = [];
    for (let col = 0; col < 3; col++) {
      const index = row * 3 + col;
      pixels[row][col] = seededRandom(hash, index) > 0.5;
    }
    // 镜像
    pixels[row][3] = pixels[row][1];
    pixels[row][4] = pixels[row][0];
  }

  // 生成 SVG
  const cellSize = size / 5;
  let svgContent = "";

  for (let row = 0; row < 5; row++) {
    for (let col = 0; col < 5; col++) {
      if (pixels[row][col]) {
        svgContent += `<rect x="${col * cellSize}" y="${row * cellSize}" width="${cellSize}" height="${cellSize}" fill="${mainColor}"/>`;
      }
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
    <rect width="${size}" height="${size}" fill="#f0f0f0"/>
    ${svgContent}
  </svg>`;
}

/**
 * 生成像素头像的 Data URL
 * @param seed - 种子字符串
 * @param size - SVG 尺寸
 * @returns Data URL 字符串
 */
export function generatePixelAvatarDataUrl(seed: string, size: number = 80): string {
  const svg = generatePixelAvatar(seed, size);
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

/**
 * 获取用户头像 URL
 * 如果用户有自定义头像则返回，否则生成默认像素头像
 * @param avatarUrl - 用户的自定义头像 URL
 * @param seed - 用于生成默认头像的种子（用户 ID 或邮箱）
 * @returns 头像 URL
 */
export function getAvatarUrl(avatarUrl: string | null | undefined, seed: string): string {
  if (avatarUrl) {
    return avatarUrl;
  }
  return generatePixelAvatarDataUrl(seed);
}
