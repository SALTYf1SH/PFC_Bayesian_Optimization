PFC 仿真服务端 (pfc_server.py) - README 使用说明
1. 概述 (Overview)
本脚本需要在 Itasca PFC 软件内部运行。它作为一个专用的服务端，负责监听来自主优化客户端 (main_optimization.py) 的网络连接。

该服务端的核心功能是：

从客户端接收一组微观参数 (例如 emod, pb_coh 等)。

使用这些参数，执行一个完整的、遵循标准流程的PFC单轴压缩试验模拟。

记录模拟过程中产生的应力-应变曲线。

将记录到的数据返回给客户端，供其进行评估和下一轮优化。

它充当了贝叶斯优化流程的计算后端，有效地允许一个外部的Python脚本来驱动PFC进行大规模的数值模拟。

2. 工作流程 (How It Works)
对于每一个模拟请求，服务端都会遵循一个严谨、有序 (sequential) 的工作流程：

初始化 (Initialization)：服务端在PFC内部启动，绑定到本地的一个网络端口 (127.0.0.1:50009)，并开始等待客户端的连接。在等待期间，PFC的用户界面(GUI)会变得无响应，这是正常现象。

接收参数 (Receive Parameters)：一旦客户端连接成功，服务端会接收到一个JSON格式的字符串，其中包含了本次模拟所需的一组微观参数。

执行模拟 (Execute Simulation)：核心函数 _run_single_simulation 被调用。该函数会严格遵循工业标准流程，执行一系列PFC命令来完成一次完整的模拟：

阶段一：生成无黏结试样: 创建一个新模型，并在由四面墙体定义的容器内生成一堆无黏结的颗粒集合体。

阶段二：压实与稳定: 通过求解模型至平衡，将无黏结的颗粒压实成一个稳定、密实的状态。随后，移除用于压实的临时侧墙。

阶段三：施加黏结: 将 linearpbond (平行黏结)接触模型应用到已经稳定的试样上。再次求解模型，以确保在加载开始前，试样处于一个无应力的黏结平衡状态。

阶段四：单轴加载: 通过让顶部和底部的墙体以恒定速度相向移动，来对试样进行压缩。

数据记录与导出 (Data Recording & Export)：

在加载阶段，脚本会使用PFC原生的 history 命令来记录每个计算步的轴向应变和轴向应力。这是通过将 history 与计算应力应变的FISH函数 (@axial_strain_wall, @axial_stress_wall) 关联来实现的。

当模拟完成后 (通常由 fish-halt 条件触发)，服务端会命令PFC将记录在内存中的历史数据导出到一个临时的文本文件 (temp_server_history.txt)。

数据读取与清理 (Data Retrieval & Cleanup)：

Python脚本随后会使用内置的标准库读取这个文本文件（无需numpy库）。

它会解析文件中的列来提取应变和应力数据，将应力单位从Pa转换为MPa，并将它们存入Python列表中。

最后，删除这个临时文件，以保持工作目录的整洁。

返回结果 (Return Results)：最终的应力-应变数据被序列化成一个JSON字符串，并通过网络连接发送回客户端。

3. 使用方法 (How to Use)
打开 Itasca PFC: 启动您的PFC2D应用程序。

设置工作目录: 确保PFC的工作目录是本项目的根目录 (PFC_Bayesian_Optimization)。这一点至关重要，否则脚本将无法在 pfc_model/ 子文件夹中找到所需的FISH文件。

运行脚本:

在PFC的命令流控制台输入 call 'source_code/pfc_server.py' 命令。

或者，在PFC的编辑器中打开 source_code/pfc_server.py 文件并执行它。

服务端就绪: PFC的控制台会显示 --- PFC Server started on 127.0.0.1:50009 --- 和 Waiting for a client connection... 等信息。此时，PFC应用已经准备就绪并处于等待状态。其图形用户界面(GUI)将会“冻结”或无响应，这是预期的正常行为。

启动客户端: 现在，您可以从一个标准的Python环境（例如VS Code, PyCharm, 或一个独立的终端）运行 main_optimization.py 脚本。客户端会自动连接到这个服务端，优化过程将随之开始。

停止服务端: 要停止服务端，您可能需要在PFC中中断脚本的运行（例如，在PFC的控制台窗口按下 Ctrl+C）。

4. 代码结构 (Code Structure)
该脚本由两个主要函数构成：

_run_single_simulation(params)
这是核心的计算引擎。

输入: 一个名为 params 的字典，包含了单次模拟所需的所有微观参数。

功能: 包含了所有的 it.command() 调用，用于执行从 model new 到 model solve 的完整PFC模拟流程。它还负责处理导出和读取历史数据文件的逻辑。

输出: 一个包含最终 'Strain' 和 'Stress' 列表的字典。如果发生错误，则返回包含空列表的字典。

start_blocking_server()
该函数处理所有与网络相关的任务。

功能: 它创建一个套接字(socket)，将其绑定到指定的IP和端口，然后进入一个无限循环 (while True) 来监听客户端的连接。当客户端连接时，它接收参数数据，调用 _run_single_simulation 获取结果，并将结果发回。

行为: 这是一个简单的“阻塞式”服务器，意味着它一次只能处理一个客户端连接。这对于本优化工作流中的一对一通信模式是完全足够的。

5. 依赖与注意事项 (Dependencies and Important Notes)
依赖:

一个已安装并启用了Python脚本功能的 Itasca PFC 版本。

所需的FISH文件 (ss_wall.fis, fracture.p2fis) 必须位于PFC工作目录下的 pfc_model 子文件夹中。

无第三方Python库: 本脚本特意只使用了PFC内置的标准Python库编写。它不需要在PFC的Python环境中安装 numpy 或任何其他外部包。

PFC无响应: 再次提醒，当本服务端脚本正在运行并等待客户端时，PFC应用程序“冻结”或无响应是正常且预期的行为。