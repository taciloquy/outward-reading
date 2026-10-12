const fs = require('fs');
const path = require('path');

const tmpDir = path.resolve('./tmp_output');
const repoRoot = path.resolve('./');

// 文件名正则：YYYY-MM-DD_001.clean.html
const fileReg = /^(\d{4}-\d{2}-\d{2})_(\d{3})\.(clean|annotated)\.html$/;

async function runArchive() {
  if (!fs.existsSync(tmpDir)) {
    console.error(`临时目录不存在：${tmpDir}`);
    return;
  }
  const files = fs.readdirSync(tmpDir);
  const resultList = [];

  for (const fname of files) {
    const match = fname.match(fileReg);
    if (!match) {
      console.log(`跳过不匹配文件：${fname}`);
      continue;
    }
    const dateStr = match[1];
    const seq = match[2];
    const type = match[3];
    const fileKey = `${dateStr}_${seq}`;
    const [y, m] = dateStr.split('-');

    // 本地归档目标目录
    const targetSubDir = path.join(repoRoot, 'articles', y, m);
    fs.mkdirSync(targetSubDir, { recursive: true });

    const srcFull = path.join(tmpDir, fname);
    const dstFull = path.join(targetSubDir, fname);
    fs.copyFileSync(srcFull, dstFull);
    console.log(`✅ 归档成功：${fname} → ${path.relative(repoRoot, dstFull)}`);

    // EdgeOne 线上相对路径，直接存入CloudBase
    const webPath = `/articles/${y}/${m}/${fname}`;
    resultList.push({
      fileKey,
      publishDate: dateStr,
      type,
      localPath: path.relative(repoRoot, dstFull),
      webPath
    });
  }

  // 按fileKey分组，合并 clean / annotated 一对文章
  const groupMap = {};
  for (const item of resultList) {
    if (!groupMap[item.fileKey]) {
      groupMap[item.fileKey] = {
        fileKey: item.fileKey,
        publishDate: item.publishDate,
        cleanPath: null,
        annotatedPath: null
      };
    }
    if (item.type === 'clean') {
      groupMap[item.fileKey].cleanPath = item.webPath;
    } else {
      groupMap[item.fileKey].annotatedPath = item.webPath;
    }
  }

  const finalArticles = Object.values(groupMap);
  console.log("\n==================== 可入库元数据JSON ====================");
  console.log(JSON.stringify(finalArticles, null, 2));
  console.log("\n💡 提示：复制上面JSON，补充 title / source / plainText 后录入CloudBase articles集合");
}

runArchive().catch(console.error);
