// 批量提取所有文章的生词，更新 index.html
const fs = require('fs');
const path = require('path');

const articlesDir = path.resolve('./articles');
const indexFile = path.resolve('./index.html');

// 1. 遍历所有 annotated 文件，提取生词
function extractVocabs(html) {
  const redWordRe = /<span style='color:#EE0000;'>([^<]+)<\/span>/g;
  const redWords = [];
  let m;
  while ((m = redWordRe.exec(html)) !== null) {
    const word = m[1].trim();
    if (!redWords.includes(word)) { // 去重
      redWords.push(word);
    }
  }
  
  const phoneticRe = /<span style='color:#1A6FB0;font-size:12pt;'>(\/[^<]+\/)<\/span>\s*<span style='color:#555555;font-size:12pt;'>([^<]+)<\/span>/g;
  const phoneticPairs = [];
  while ((m = phoneticRe.exec(html)) !== null) {
    phoneticPairs.push({ phonetic: m[1].trim(), definition: m[2].replace(/^[\s ]+/, '').trim() });
  }
  
  const vocabs = [];
  const count = Math.min(redWords.length, phoneticPairs.length);
  for (let i = 0; i < count; i++) {
    vocabs.push({
      word: redWords[i],
      phonetic: phoneticPairs[i].phonetic,
      definition: phoneticPairs[i].definition
    });
  }
  return vocabs;
}

// 2. 遍历所有 annotated 文件
const vocabsMap = {}; // fileKey -> vocabs
function walkDir(dir) {
  const files = fs.readdirSync(dir);
  for (const f of files) {
    const fullPath = path.join(dir, f);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walkDir(fullPath);
    } else if (f.endsWith('.annotated.html')) {
      const match = f.match(/^(\d{4}-\d{2}-\d{2}_\d{3})\.annotated\.html$/);
      if (match) {
        const fileKey = match[1];
        const html = fs.readFileSync(fullPath, 'utf8');
        const vocabs = extractVocabs(html);
        vocabsMap[fileKey] = vocabs;
        console.log(`${fileKey}: 提取了 ${vocabs.length} 个生词`);
      }
    }
  }
}

walkDir(articlesDir);
console.log(`\n共提取了 ${Object.keys(vocabsMap).length} 篇文章的生词`);

// 3. 更新 index.html
let html = fs.readFileSync(indexFile, 'utf8');

// 找到每篇文章的 vocabs 字段，替换成新的
for (const [fileKey, vocabs] of Object.entries(vocabsMap)) {
  // 找到文章对象，替换 vocabs 字段
  const vocabsStr = vocabs.length > 0 
    ? vocabs.map(v => `{word:"${v.word}",phonetic:"${v.phonetic}",definition:"${v.definition}"}`).join(',\n          ')
    : '';
  
  // 匹配 fileKey 对应的文章对象中的 vocabs: [...]
  const regex = new RegExp(`(fileKey: "${fileKey}"[\\s\\S]*?vocabs: \\[)[\\s\\S]*?(\\])`);
  html = html.replace(regex, `$1\n          ${vocabsStr}\n        $2`);
}

fs.writeFileSync(indexFile, html);
console.log('\n已更新 index.html');
