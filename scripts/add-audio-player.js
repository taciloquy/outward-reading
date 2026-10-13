const fs = require('fs');
const filePath = '/Volumes/WORK DISK/outward-reading-site/index.html';
let content = fs.readFileSync(filePath, 'utf8');

// 1. 在 data 里加 showAudioPlayer 变量
content = content.replace(
  'showUploadModal: false,',
  'showUploadModal: false,\n        showAudioPlayer: false,'
);

// 2. 在按钮组里加播放音频按钮
content = content.replace(
  '<button @click="showUploadModal=true" title="上传音频" style="padding:8px 12px;">📤</button>',
  '<button @click="showUploadModal=true" title="上传音频" style="padding:8px 12px;">📤</button>\n          <button @click="openAudioPlayer()" title="播放音频" style="padding:8px 12px;">🎵</button>'
);

// 3. 在 methods 里加 openAudioPlayer 和 deleteAudio 方法
content = content.replace(
  'clearCache(){',
  '// 打开播放音频弹窗\n      openAudioPlayer(){\n        this.showAudioPlayer = true;\n        this.loadUploadedAudios(this.currentArticle.fileKey);\n      },\n      // 删除音频\n      deleteAudio(audioId){\n        if (!confirm("确定要删除这个音频吗？")) return;\n        const request = indexedDB.open("audioDB", 1);\n        request.onsuccess = (e) => {\n          const db = e.target.result;\n          const transaction = db.transaction(["audios"], "readwrite");\n          const store = transaction.objectStore("audios");\n          store.delete(audioId);\n          alert("删除成功！");\n          this.loadUploadedAudios(this.currentArticle.fileKey);\n        };\n      },\n      clearCache(){'
);

// 4. 在上传音频弹窗后面加播放音频弹窗
content = content.replace(
  '<!-- 上传音频弹窗 -->',
  '<!-- 播放音频弹窗 -->\n    <div v-if="showAudioPlayer" class="modal" @click.self="showAudioPlayer=false">\n      <div class="modal-card">\n        <span class="close-btn" @click="showAudioPlayer=false">✕</span>\n        <h3>播放音频</h3>\n        \n        <!-- AI 音频 -->\n        <div style="margin:1rem 0;padding:1rem;border:1px solid #ddd;border-radius:8px;">\n          <strong>AI 朗读</strong>\n          <p style="color:#666;font-size:0.9rem;margin:0.5rem 0 0 0;">使用浏览器自带的 AI 语音朗读文章</p>\n        </div>\n        \n        <!-- 用户上传的音频 -->\n        <div style="margin:1rem 0;">\n          <strong>已上传的音频</strong>\n          <div v-if="uploadedAudios.length === 0" style="color:#999;margin-top:0.5rem;">暂无上传的音频</div>\n          <div v-for="audio in uploadedAudios" :key="audio.id" style="margin:0.5rem 0;padding:0.8rem;border:1px solid #ddd;border-radius:8px;">\n            <div style="display:flex;justify-content:space-between;align-items:center;">\n              <div>\n                <strong>{{audio.uploaderName}}</strong>\n                <span style="color:#999;font-size:0.85rem;margin-left:8px;">{{audio.fileName}}</span>\n              </div>\n              <div>\n                <button @click="playAudio(audio)" style="padding:4px 12px;cursor:pointer;margin-right:8px;">播放</button>\n                <button @click="deleteAudio(audio.id)" style="padding:4px 12px;cursor:pointer;color:red;">删除</button>\n              </div>\n            </div>\n          </div>\n        </div>\n        \n        <button @click="showAudioPlayer=false" style="padding:8px 16px;cursor:pointer;">关闭</button>\n      </div>\n    </div>\n\n    <!-- 上传音频弹窗 -->'
);

// 5. 加 playAudio 方法
content = content.replace(
  '// 打开播放音频弹窗\n      openAudioPlayer(){',
  '// 播放音频\n      playAudio(audio){\n        const audioEl = new Audio(audio.audioData);\n        audioEl.play();\n      },\n      // 打开播放音频弹窗\n      openAudioPlayer(){'
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('✅ 已添加播放和删除音频功能');
