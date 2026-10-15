# 第一次上传 GitHub

## 你需要准备

1. 一个自己的 GitHub 账号，并在浏览器登录。不需要把密码或访问令牌发给任何人。
2. 安装 GitHub Desktop（https://desktop.github.com/），在软件里通过浏览器登录。
3. 仓库建议命名 `yukina-manga-reader`；首次保留私有（Private），以后可另行决定是否公开。
4. 开源许可证尚未选定。当前不是必须公开或发布安装包的阶段。

## 推荐图形操作

当前本机准备目录已加入 GitHub Desktop；首次本地提交完成后即可使用 Publish repository。仓库现已发布到 GitHub 私有仓库，远程名为 origin；后续修改完成本地提交后用 Push origin 更新。ZIP 不包含 Git 历史，解压后仍需创建仓库及首次提交。

1. 解压准备 ZIP 到长期使用的目录，或直接使用已准备的目录。ZIP 不含 .git，使用 ZIP 时先将解压得到的文件夹改名为 yukina-manga-reader，再在 GitHub Desktop 用 File → New Repository，Name 填 yukina-manga-reader，Local path 选它的父目录（不要再选 yukina-manga-reader 本身），不额外生成 README 或许可证；不要选择整个“开发程序”父目录。直接使用准备目录则用 File → Add Local Repository。
2. 查看 Changes：应只有 desktop、android、macos、docs、tools 和根部说明。不得含 .tools、.venv、data、cache、签名密钥、个人书籍或其他软件。
3. 若 History 已有首次提交且 Changes 为空，可跳过本步。否则在 Summary 输入 `Initial source import`，点击 Commit。GitHub Desktop 提示时配置你的提交名及 GitHub 提供的 noreply 邮箱，可避免公开真实邮箱。
4. 点击 Publish repository，名称填写 `yukina-manga-reader`，保留 Keep this code private。点击最终 Publish 前确认文件列表和可见性；该动作才会把代码上传到账号。
5. 以后修改代码 → 查看 Changes → 填写摘要 Commit → Push origin。其他电脑先 Clone，再 Fetch/Pull。此准备目录不是原开发目录的自动镜像。

不要把 ZIP 本身作为唯一文件上传；GitHub 应当能直接看到各个源码文件。当前不需要同时使用命令行上传，也无需创建 Access Token。

## 安装包与密钥

源码进入仓库；APK/EXE 等以后放 GitHub Releases，先不混入源码提交。此准备包没有自动发布工作流，不会推送或发布安装包。

现有 Android 开发 keystore 位于原安卓项目 .tools 下，已排除。你应将其单独做离线备份，切勿放进 GitHub；这是以后覆盖更新现有平板应用的关键。新克隆会生成另一把开发密钥，不能覆盖原签名安装，也不应通过卸载丢弃现有书库。

官方流程：https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop
