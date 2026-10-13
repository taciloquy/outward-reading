const fs = require('fs');
const filePath = '/Volumes/WORK DISK/outward-reading-site/index.html';
let content = fs.readFileSync(filePath, 'utf8');

// 找到之前修改的地方，改成去掉 h1 和 subtitle
content = content.replace(
  "// 去掉文章里的header-bar（灰色小标题）\n            html = html.replace(/<div class='header-bar'>[\\s\\S]*?<\\/div>/, \"\");",
  "// 去掉文章里的header-bar、h1和subtitle（重复的标题）\n            html = html.replace(/<div class='header-bar'>[\\s\\S]*?<\\/div>/, \"\");\n            html = html.replace(/<h1>[\\s\\S]*?<\\/h1>/, \"\");\n            html = html.replace(/<div class='subtitle'>[\\s\\S]*?<\\/div>/, \"\");"
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('✅ 已修改 index.html');
