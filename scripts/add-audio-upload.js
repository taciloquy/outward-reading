const fs = require('fs');
const filePath = '/Volumes/WORK DISK/outward-reading-site/index.html';
let content = fs.readFileSync(filePath, 'utf8');

// 1. 在按钮组里添加上传音频的按钮
content = content.replace(
  '<button @click="printArticle()" title="打印" style="padding:8px 12px;">🖨</button>',
  '<button @click="printArticle()" title="打印" style="padding:8px 12px;">🖨</button>\n          <button @click="showUploadModal=true" title="上传音频" style="padding:8px 12px;">📤</button>'
);

// 2. 在 data 里添加上传相关的变量
content = content.replace(
  'articleHtml: ""',
  'articleHtml: "",\n        showUploadModal: false,\n        uploaderName: localStorage.getItem("uploaderName") || "",\n        uploadedAudios: []'
);

// 3. 在 methods 里添加上传相关的方法
content = content.replace(
  'clearCache(){',
  '// 上传音频\n      async uploadAudio(){\n        const file = this.$refs.audioFile.files[0];\n        if (!file) {\n          alert("请选择音频文件");\n          return;\n        }\n        if (!this.uploaderName.trim()) {\n          alert("请输入上传者名字");\n          return;\n        }\n        localStorage.setItem("uploaderName", this.uploaderName);\n        \n        // 读取文件并保存到 IndexedDB\n        const reader = new FileReader();\n        reader.onload = (e) => {\n          const audioData = e.target.result;\n          const articleId = this.currentArticle.fileKey;\n          \n          // 保存到 IndexedDB\n          this.saveAudioToDB(articleId, this.uploaderName, audioData, file.name);\n          \n          alert("上传成功！");\n          this.showUploadModal = false;\n          this.loadUploadedAudios(articleId);\n        };\n        reader.readAsDataURL(file);\n      },\n      // 保存音频到 IndexedDB\n      saveAudioToDB(articleId, uploaderName, audioData, fileName){\n        const request = indexedDB.open("audioDB", 1);\n        request.onupgradeneeded = (e) => {\n          const db = e.target.result;\n          db.createObjectStore("audios", { keyPath: "id", autoIncrement: true });\n        };\n        request.onsuccess = (e) => {\n          const db = e.target.result;\n          const transaction = db.transaction(["audios"], "readwrite");\n          const store = transaction.objectStore("audios");\n          store.add({\n            articleId: articleId,\n            uploaderName: uploaderName,\n            audioData: audioData,\n            fileName: fileName,\n            uploadTime: new Date().getTime()\n          });\n        };\n      },\n      // 加载已上传的音频\n      loadUploadedAudios(articleId){\n        const request = indexedDB.open("audioDB", 1);\n        request.onsuccess = (e) => {\n          const db = e.target.result;\n          const transaction = db.transaction(["audios"], "readonly");\n          const store = transaction.objectStore("audios");\n          const index = store.index("articleId");\n          const query = index.getAll(articleId);\n          query.onsuccess = (e) => {\n            this.uploadedAudios = e.target.result;\n          };\n        };\n      },\n      clearCache(){'
);

// 4. 在弹窗里添加上传音频的弹窗
content = content.replace(
  '<div v-if="showVocab" class="modal" @click.self="showVocab=false">',
  '<!-- 上传音频弹窗 -->\n    <div v-if="showUploadModal" class="modal" @click.self="showUploadModal=false">\n      <div class="modal-card">\n        <span class="close-btn" @click="showUploadModal=false">✕</span>\n        <h3>上传音频</h3>\n        <div style="margin:1rem 0;">\n          <label>上传者名字：</label>\n          <input v-model="uploaderName" placeholder="输入你的名字" style="padding:6px;margin-left:8px;">\n        </div>\n        <div style="margin:1rem 0;">\n          <label>选择音频文件：</label>\n          <input ref="audioFile" type="file" accept="audio/*" style="margin-left:8px;">\n        </div>\n        <button @click="uploadAudio()" style="padding:8px 16px;cursor:pointer;">上传</button>\n      </div>\n    </div>\n\n    <div v-if="showVocab" class="modal" @click.self="showVocab=false">'
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('✅ 已添加上传音频功能');
