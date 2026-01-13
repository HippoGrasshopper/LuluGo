import os

# 目标目录
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

print(f"正在检查目录: {static_dir}\n")

if not os.path.exists(static_dir):
    print("❌ 严重错误: static 文件夹不存在！")
    exit()

files = os.listdir(static_dir)
print(f"当前目录下的文件: {files}")

# 检查 wgo.min.js
target = "wgo.min.js"
target_path = os.path.join(static_dir, target)

# 1. 检查是否存在
if target not in files:
    print(f"\n❌ 错误: 找不到 {target}！")
    # 检查是不是常见的命名错误
    for f in files:
        if "wgo" in f and f != target:
            print(f"   -> 发现疑似文件: '{f}' (是不是多写了后缀，比如 .js.txt？)")
else:
    print(f"\n✅ 文件名检查通过: {target}")
    
    # 2. 检查大小
    size = os.path.getsize(target_path)
    print(f"   文件大小: {size} bytes ({size/1024:.2f} KB)")
    
    if size < 100:
        print("❌ 错误: 文件太小了！里面可能没有代码，或者是空的。")
    
    # 3. 检查文件头 (最关键的一步)
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read(50) # 只读前50个字符
            print(f"   文件开头内容: [{content}]")
            
            if content.strip().startswith("<!DOCTYPE html>"):
                print("❌ 错误: 这不是 JS 文件！这是 HTML 网页（可能是 404 页面被你保存下来了）。")
            elif not content.strip():
                print("❌ 错误: 文件是空的！")
            else:
                print("✅ 文件头检查看起来正常 (是代码)。")
    except Exception as e:
        print(f"❌ 读取文件失败: {e} (可能是编码问题)")

print("\n------------------------------")
print("分析结束。请根据上面的红叉 ❌ 修改问题。")