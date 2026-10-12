// 从 annotated HTML 中提取生词表（词 + 音标 + 中文释义）
// 用法: node scripts/extract-vocabs.js <annotated.html路径>
// 输出: stdout 打印 JSON 数组，可直接录入 CloudBase vocab 集合

const fs = require('fs');
const path = require('path');

const file = process.argv[2] || path.resolve('./articles/2026/10/2026-10-12_001.annotated.html');
const html = fs.readFileSync(file, 'utf8');

// 1) 按文档顺序提取所有红色重点词 (#EE0000) —— 这些是有音标的词
const redWordRe = /<span style='color:#EE0000;'>([^<]+)<\/span>/g;
const redWords = [];
let m;
while ((m = redWordRe.exec(html)) !== null) {
  redWords.push(m[1].trim());
}

// 2) 按文档顺序提取所有"音标+紧跟中文释义"对
//    音标 span: color:#1A6FB0，内容形如 /slʌm/
//    中文 span: color:#555555，内容形如 "  贫民窟"
const phoneticRe = /<span style='color:#1A6FB0;font-size:8\.5pt;'>(\/[^<]+\/)<\/span>\s*<span style='color:#555555;font-size:8\.5pt;'>([^<]+)<\/span>/g;
const phoneticPairs = [];
while ((m = phoneticRe.exec(html)) !== null) {
  phoneticPairs.push({ phonetic: m[1].trim(), definition: m[2].replace(/^[\s ]+/, '').trim() });
}

// 3) 按顺序把 redWords[i] 与 phoneticPairs[i] 配对
const vocabs = [];
const count = Math.min(redWords.length, phoneticPairs.length);
for (let i = 0; i < count; i++) {
  vocabs.push({
    word: redWords[i],
    phonetic: phoneticPairs[i].phonetic,
    definition: phoneticPairs[i].definition
  });
}

console.log('红色词数:', redWords.length, ' 音标对:', phoneticPairs.length, ' 提取生词数:', vocabs.length);
console.log('\n===== VOCAB JSON (可直接录入 vocab 集合) =====');
console.log(JSON.stringify(vocabs, null, 2));
