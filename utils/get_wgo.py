import os
import urllib.request
import ssl

# 目标文件夹
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

print(f"准备下载 WGo.js 到: {static_dir}")

# 策略：直接从 WGo 作者的官网演示地址下载
# 如果官网慢，这里还准备了一个备用的 GitHub 链接（来自 reliable 的 fork）
sources = [
    {
        "name": "官方源 (waltheri.net)",
        "files": {
            "wgo.min.js": "http://wgo.waltheri.net/wgo/wgo.min.js",
            "wgo.player.min.js": "http://wgo.waltheri.net/wgo/wgo.player.min.js"
        }
    },
    {
        "name": "备用源 (GitHub Raw)",
        "files": {
            "wgo.min.js": "https://raw.githubusercontent.com/kuehnelth/wgo.js/master/wgo.min.js",
            "wgo.player.min.js": "https://raw.githubusercontent.com/kuehnelth/wgo.js/master/wgo.player.min.js"
        }
    }
]

# 忽略 SSL 验证
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
headers = {'User-Agent': 'Mozilla/5.0'}

def download_file(url, path):
    print(f"  正在下载: {url}")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response, open(path, 'wb') as out_file:
        out_file.write(response.read())
    
    # 简单的完整性检查
    if os.path.getsize(path) < 1000:
        raise Exception("文件过小")

# 开始下载
for source in sources:
    print(f"\n尝试使用: {source['name']} ...")
    success_count = 0
    
    for filename, url in source["files"].items():
        filepath = os.path.join(static_dir, filename)
        try:
            download_file(url, filepath)
            print(f"  ✅ {filename} 下载成功！")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 下载失败: {e}")
            break # 只要有一个失败，就换下一个源
    
    if success_count == 2:
        print("\n🎉 全部下载完成！")
        break
else:
    print("\n❌ 所有源都失败了。请尝试下面的“手动下载”。")

print("--------------------------------")
print("请刷新浏览器 (Ctrl+F5) 测试。")