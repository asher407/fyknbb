# 微博爬虫与数据分析

## TODO list

- [x] 写取爬虫模块
  - [x] 爬取 2025 的静态数据
  - [x] 爬取当时的实时数据
  - [x] “那年今日”：根据用户提供的日期获得历史热搜
- [x] 完成数据读取模块
  - [x] 设计类似于数据库的数据读取方法
- [x] 数据清洗与图表展示
  - [x] 静态的预先数据分析与绘制
  - [x] 完成一部分没有类别的数据分类
  - [x] 按照用户选择的数据进行动态分析与绘制
  - [x] 关键词关系网络图 可视化
- [x] 数据分析模块
  - [x] 制作某个关键词或类型热度随时间变化的展示
  - [x] 热搜情感色彩分析
  - [x] 年度报告汇总 （构建热度指数）
- [x] 完成 gui 前端展示模块

## 代码规范

模块化代码结构，模块之间解耦。
每个类定义的方法需要有标准的用户手册（内容包括方法的功能，输入的参数，输出的结果以及内部简单的逻辑。
所有的模块都需要设计一个比较典型的测试案例，便于后续更改代码逻辑时确保功能不发生变化以及保证方法 api 的稳定性。

## 项目说明

### quick start

#### linux

```bash
# 给脚本添加执行权限（首次运行）
chmod +x run.sh
chmod +x run.py

# 使用shell脚本启动
./run.sh

# 或使用Python脚本启动
python run.py
```

#### windows

```bash
# 使用Python脚本启动
python run.py
```

#### 高级选项

```bash
# 只检查环境，不启动GUI
python run.py --check

# 安装缺失的依赖
python run.py --install

# 安装playwright浏览器
python run.py --install-browser

# 跳过环境检查直接启动GUI
python run.py --no-check
```
