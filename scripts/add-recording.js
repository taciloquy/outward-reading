const fs = require('fs');
const filePath = '/Volumes/WORK DISK/outward-reading-site/index.html';
let content = fs.readFileSync(filePath, 'utf8');

// 1. 在 data 里加录音相关的变量
content = content.replace(
  'showAudioPlayer: false,',
  'showAudioPlayer: false,\n        isRecording: false,\n        mediaRecorder: null,\n        recordedChunks: [],\n        recordingTimer: null,\n        recordingSeconds: 0,'
);

// 2. 在按钮组里加录音按钮
content = content.replace(
  '<button @click="showUploadModal=true" title="上传音频" style="padding:8px 12px;">📤</button>',
  '<button @click="startRecording()" :title="isRecording ? \'停止录音\' : \'直接录音\'" style="padding:8px 12px;" v-if="!isRecording">🎙</button>\n          <button @click="stopRecording()" :title="\'停止录音 (\' + recordingSeconds + \'秒)\'" style="padding:8px 12px;background:#ff4444;color:white;" v-else>⏱ {{recordingSeconds}}s</button>'
);

// 3. 在 methods 里加录音相关的方法
content = content.replace(
  '// 打开播放音频弹窗\n      openAudioPlayer(){',
  '// 开始录音\n      async startRecording(){\n        try {\n          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });\n          this.mediaRecorder = new MediaRecorder(stream);\n          this.recordedChunks = [];\n          \n          this.mediaRecorder.ondataavailable = (e) => {\n            if (e.data.size > 0) this.recordedChunks.push(e.data);\n          };\n          \n          this.mediaRecorder.onstop = () => {\n            const blob = new Blob(this.recordedChunks, { type: \'audio/webm\' });\n            const reader = new FileReader();\n            reader.onload = (e) => {\n              const audioData = e.target.result;\n              const articleId = this.currentArticle.fileKey;\n              const uploaderName = this.uploaderName || "匿名";\n              \n              // 保存到 IndexedDB\n              this.saveAudioToDB(articleId, uploaderName, audioData, "录音_" + new Date().toLocaleTimeString() + ".webm");\n              \n              alert("录音完成，已保存！");\n            };\n            reader.readAsDataURL(blob);\n            \n            // 停止所有轨道\n            stream.getTracks().forEach(track => track.stop());\n          };\n          \n          this.mediaRecorder.start();\n          this.isRecording = true;\n          this.recordingSeconds = 0;\n          this.recordingTimer = setInterval(() => {\n            this.recordingSeconds++;\n          }, 1000);\n        } catch (err) {\n          alert("无法访问麦克风：" + err.message);\n        }\n      },\n      // 停止录音\n      stopRecording(){\n        if (this.mediaRecorder && this.isRecording) {\n          this.mediaRecorder.stop();\n          this.isRecording = false;\n          clearInterval(this.recordingTimer);\n        }\n      },\n      // 打开播放音频弹窗\n      openAudioPlayer(){'
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('✅ 已添加网页直接录音功能');
