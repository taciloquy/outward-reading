const fs = require('fs');
const filePath = '/Volumes/WORK DISK/outward-reading-site/index.html';
let content = fs.readFileSync(filePath, 'utf8');

// 找到 this.articleHtml = html; 这一行，在它之前加一行处理代码
content = content.replace(
  'this.articleHtml = html;',
  '// 去掉文章里的header-bar（灰色小标题）\n            html = html.replace(/<div class=\'header-bar\'>[\\s\\S]*?<\\/div>/, "");\n            this.articleHtml = html;'
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('✅ 已修改 index.html');
