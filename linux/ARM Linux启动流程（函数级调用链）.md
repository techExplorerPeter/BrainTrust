ARM Linux启动流程（函数级调用链）
│
├─── **1. 硬件上电与Boot ROM阶段**
│   │
│   ├─── 硬件复位与初始化
│   │   ├─── CPU进入Reset异常向量（ARM异常向量表基址0x0或0xffff0000）
│   │   │   └─── 汇编代码：arch/arm/kernel/entry-armv.S:reset_handler
│   │   │
│   │   ├─── 关闭Cache和MMU
│   │   │   ├─── 汇编指令：MCR p15,0,r0,c7,c5,0 （ invalidate icache）
│   │   │   └─── 汇编指令：MRC p15,0,r0,c1,c0,0; BIC r0,r0,#1 （ disable MMU）
│   │   │
│   │   └─── 初始化栈空间（SP指针）
│   │       └─── 汇编代码：设置SVC模式栈，arch/arm/kernel/entry-armv.S
│   │
│   └─── Boot ROM固件（厂商固化，如ARM Trusted Firmware）
│       ├─── 加载Boot Loader到RAM
│       │   ├─── 从启动设备（eMMC/SD卡）读取U-Boot镜像
│       │   └─── 复制镜像到指定内存地址（如0x80000000）
│       │
│       └─── 跳转执行Boot Loader
│           └─── 汇编指令：BX BootLoader入口地址
│
├─── **2. 引导加载程序阶段（以U-Boot为例）**
│   │
│   ├─── Stage 1：汇编初始化（arch/arm/cpu/armv7/start.S）
│   │   ├─── 异常向量表初始化
│   │   │   └─── 定义Reset、Undefined、IRQ等异常处理入口
│   │   │
│   │   ├─── 内存控制器初始化
│   │   │   ├─── 配置DDR时序：arch/arm/cpu/armv7/mx6/sdram.c:mx6_sdram_initialize
│   │   │   └─── 初始化MMU页表（临时）
│   │   │
│   │   ├─── 串口初始化
│   │   │   ├─── 配置UART控制器：drivers/serial/serial.c:serial_initialize
│   │   │   └─── 设置波特率、数据位等参数
│   │   │
│   │   └─── 加载Stage 2到RAM
│   │       ├─── 从Flash/SD卡读取U-Boot第二阶段镜像
│   │       └─── 跳转执行：ldr pc, =stage2_entry
│   │
│   ├─── Stage 2：C代码初始化（lib_arm/board.c:start_armboot）
│   │   ├─── 硬件设备初始化
│   │   │   ├─── 初始化NAND/SD卡：drivers/mtd/nand/nand_base.c:nand_init
│   │   │   ├─── 初始化USB：drivers/usb/usb_main.c:usb_init
│   │   │   └─── 初始化网络：drivers/net/eth.c:eth_initialize
│   │   │
│   │   ├─── 设备树解析
│   │   │   ├─── 读取.dtb文件：drivers/of/fdt.c:fdt_init
│   │   │   └─── 验证设备树：drivers/of/fdt.c:fdt_validate
│   │   │
│   │   ├─── 加载Linux内核
│   │   │   ├─── 从存储设备读取内核镜像：common/cmd_load.c:do_load
│   │   │   └─── 解压缩内核（如zImage）：lib/decompress.c:decompress
│   │   │
│   │   ├─── 传递启动参数
│   │   │   ├─── 构建cmdline：board/arm/yourboard/yourboard.c:setup_args
│   │   │   └─── 设置启动参数地址：arch/arm/lib/bootm.c:do_bootm_linux
│   │   │
│   │   └─── 跳转启动内核
│   │       └─── 汇编调用：arm/linux/bootm.c:bootm_linux
│   │
│   └─── 关键函数调用链
│       ├─── start_armboot()
│       │   ├─── board_init()
│       │   ├─── device_tree_init()
│       │   ├─── load_kernel_image()
│       │   └─── bootm_linux()
│
├─── **3. 内核初始化阶段（kernel_init）**
│   │
│   ├─── 内核解压缩与架构初始化（arch/arm/kernel/head.S）
│   │   ├─── 解压缩内核镜像（如zImage）
│   │   │   └─── 汇编解压缩代码：arch/arm/boot/compressed/head.S
│   │   │
│   │   ├─── ARM架构初始化
│   │   │   ├─── 配置页表：arch/arm/mm/proc-v7.S:create_page_tables
│   │   │   ├─── 启用MMU：arch/arm/mm/proc-v7.S:enable_mmu
│   │   │   ├─── 初始化GIC中断控制器：drivers/interrupts/gic.c:gic_init
│   │   │   └─── 多核启动：arch/arm/kernel/smp.c:smp_init
│   │   │
│   │   └─── 跳转到C语言入口：start_kernel()
│   │       └─── 定义于init/main.c:start_kernel
│   │
│   ├─── 内核C语言初始化（init/main.c:start_kernel）
│   │   ├─── 调度器初始化：sched_init()
│   │   │   └─── kernel/sched/core.c:sched_init
│   │   │
│   │   ├─── 内存管理初始化：mm_init()
│   │   │   ├─── 伙伴系统初始化：mm/page_alloc.c:page_alloc_init
│   │   │   ├─── slab分配器初始化：mm/slab.c:kmem_cache_init
│   │   │   └─── 高端内存映射：mm/highmem.c:highmem_init
│   │   │
│   │   ├─── 设备模型初始化：device_tree_init()
│   │   │   ├─── 解析设备树：drivers/of/fdt.c:of_platform_default_populate
│   │   │   ├─── 注册平台总线：drivers/base/platform.c:platform_bus_init
│   │   │   └─── 匹配设备与驱动：drivers/base/dd.c:driver_probe_device
│   │   │
│   │   ├─── 驱动子系统初始化：drivers_init()
│   │   │   ├─── 初始化PCI/USB总线：drivers/pci/pci.c:pci_subsystem_init
│   │   │   ├─── 注册字符设备驱动：drivers/char/char_dev.c:register_chrdev
│   │   │   └─── 初始化块设备：drivers/block/genhd.c:block_device_init
│   │   │
│   │   ├─── 文件系统初始化：filesystem_init()
│   │   │   ├─── 注册ext4文件系统：fs/ext4/ext4_init
│   │   │   ├─── 挂载rootfs：fs/namespace.c:mount_root
│   │   │   │   ├─── 解析root=参数：fs/cmdline.c:parse_cmdline
│   │   │   │   └─── 调用具体文件系统mount函数
│   │   │   └─── 初始化tmpfs：fs/tmpfs/inode.c:tmpfs_init
│   │   │
│   │   ├─── 网络子系统初始化：net_init()
│   │   │   ├─── 初始化TCP/IP协议栈：net/ipv4/af_inet.c:inet_init
│   │   │   ├─── 注册网络设备：drivers/net/ethernet/ethernet.c:register_netdevice
│   │   │   └─── 配置DHCP：net/ipv4/dhcpcd.c:dhcpcd_init
│   │   │
│   │   └─── 启动init进程：kernel_thread(init_post, NULL, CLONE_FS)
│   │       └─── init_post()定义于init/main.c
│   │
│   └─── 设备驱动加载流程（以GPIO驱动为例）
│       ├─── 设备树匹配：of_device_match_table
│       │   └─── drivers/gpio/gpiolib-of.c:of_gpiochip_add
│       │
│       ├─── 驱动注册：platform_driver_register()
│       │   └─── drivers/base/platform.c:platform_driver_register
│       │
│       ├─── 设备探测：driver_probe_device()
│       │   └─── drivers/base/dd.c:driver_probe_device
│       │
│       └─── 硬件操作函数：gpio_request(), gpio_set_value()
│           ├─── drivers/gpio/gpiolib.c:gpio_request
│           └─── drivers/gpio/gpiolib.c:gpio_set_value
│
├─── **4. 用户空间启动阶段（systemd流程）**
│   │
│   ├─── init进程启动（PID=1，init/main.c:init_post）
│   │   ├─── 解析启动参数，确定init程序（如/systemd）
│   │   ├─── 挂载系统文件系统：
│   │   │   ├─── mount -t proc proc /proc
│   │   │   ├─── mount -t sysfs sysfs /sys
│   │   │   └─── mount -t devtmpfs devtmpfs /dev
│   │   │
│   │   └─── 执行init程序：do_execve()
│   │       └─── 系统调用：kernel/sys.c:sys_execve
│   │
│   ├─── systemd主流程（src/core/main.c:main）
│   │   ├─── 解析命令行参数：parse_arguments()
│   │   ├─── 初始化日志系统：log_init()
│   │   ├─── 加载单元配置：load_unit_files()
│   │   │   ├─── 解析.target文件：src/core/unit.c:unit_load
│   │   │   └─── 构建依赖图：src/core/dependency.c:resolve_dependencies
│   │   │
│   │   ├─── 启动基本系统服务：
│   │   │   ├─── systemd-udevd.service：src/udev/udevd.c:main
│   │   │   ├─── systemd-journald.service：src/journal/journald.c:main
│   │   │   └─── systemd-networkd.service：src/network/networkd.c:main
│   │   │
│   │   ├─── 激活默认目标（如multi-user.target）
│   │   │   ├─── 解析.target依赖：src/core/unit.c:unit_activate
│   │   │   ├─── 并行启动服务：src/core/job.c:job_execute
│   │   │   └─── 等待服务就绪：src/core/manager.c:manager_wait_for_dependencies
│   │   │
│   │   └─── 启动登录服务：
│   │       ├─── getty@.service：src/login/getty.c:main
│   │       └─── lightdm.service（图形界面）：src/lightdm/lightdm.c:main
│   │
│   └─── 函数调用链示例（启动网络服务）
│       ├─── systemd_main()
│       │   ├─── manager_load_unit()
│       │   ├─── unit_activate()
│       │   ├─── job_queue()
│       │   └─── exec_service() → 调用networkctl启动网络
│
└─── **5. 应用程序与系统交互（函数级）**
    │
    ├─── 终端交互（Shell命令执行）
    │   ├─── 用户输入命令（如ls）
    │   │   └─── shell解析：bash/src/eval.c:eval_command
    │   │
    │   ├─── 执行程序：fork() + execve()
    │   │   ├─── fork系统调用：kernel/fork.c:do_fork
    │   │   └─── execve系统调用：kernel/exec.c:do_execve
    │   │
    │   └─── 程序运行：libc函数 → 系统调用
    │       ├─── printf() → write() → sys_write
    │       └─── open() → sys_open（定义于arch/arm/kernel/sys_arm.c）
    │
    ├─── 设备访问流程（以串口为例）
    │   ├─── 打开设备：fd = open("/dev/ttyAMA0", O_RDWR)
    │   │   └─── 系统调用：fs/open.c:do_sys_open
    │   │
    │   ├─── 配置参数：ioctl(fd, TCSETS, &termios)
    │   │   └─── 驱动处理：drivers/tty/serial/8250/8250.c:serial8250_ioctl
    │   │
    │   └─── 读写数据：read(fd, buf, len) / write(fd, buf, len)
    │       ├─── 系统调用：fs/read_write.c:vfs_read/vfs_write
    │       └─── 驱动处理：drivers/tty/serial/8250/8250.c:serial8250_read/serial8250_write
    │
    ├─── 网络应用交互（Socket编程）
    │   ├─── 创建Socket：sock = socket(AF_INET, SOCK_STREAM, 0)
    │   │   └─── 系统调用：net/socket.c:sys_socket
    │   │
    │   ├─── 绑定地址：bind(sock, &addr, len)
    │   │   └─── 系统调用：net/ipv4/af_inet.c:inet_bind
    │   │
    │   ├─── 监听连接：listen(sock, backlog)
    │   │   └─── 系统调用：net/core/sock.c:sys_listen
    │   │
    │   └─── 数据收发：send(sock, data, len, 0) / recv(...)
    │       ├─── 系统调用：net/core/sock.c:sys_sendto/sys_recvfrom
    │       └─── 协议处理：net/ipv4/tcp.c:tcp_sendmsg/tcp_recvmsg
    │
    └─── 系统调用在内核中的处理（以ARM为例）
        ├─── 用户态陷入内核：SWI指令或SVC指令（ARMv8）
        │   └─── 异常向量：arch/arm/kernel/entry-armv.S:svc_entry
        │
        ├─── 系统调用分发：
        │   ├─── 解析SWI号：arch/arm/kernel/call-sysv.S:sys_call
        │   └─── 查找系统调用表：arch/arm/kernel/sys_arm.c:sys_call_table
        │
        └─── 具体系统调用处理：
            ├─── 如sys_open：fs/open.c:do_sys_open
            └─── 如sys_write：fs/read_write.c:sys_write

关键技术点与源码映射
1. ARM启动阶段的函数调用核心
异常向量处理：ARMv7的Reset异常处理在arch/arm/kernel/entry-armv.S中，通过reset_handler函数完成底层初始化。
U-Boot Stage1：汇编代码位于arch/arm/cpu/armv7/start.S，核心函数start_armboot是Stage2的入口。
内核架构初始化：arch/arm/kernel/head.S中的__create_page_tables和__enable_mmu是MMU启用的关键函数。
2. 设备驱动加载的函数链
设备树解析：drivers/of/fdt.c中的of_platform_default_populate会遍历设备树节点，为每个节点匹配驱动。
驱动注册与探测：platform_driver_register注册驱动时，会调用driver_probe_device，该函数会触发驱动的probe函数（如gpiochip_probe）。
3. systemd启动的关键函数
单元加载：src/core/unit.c中的unit_load负责解析.service和.target文件，构建依赖关系。
并行启动：src/core/job.c中的job_execute实现服务的并行启动，通过fork()和exec()执行具体服务程序。
4. 系统调用在ARM上的实现
异常机制：ARM通过SWI（ARMv7）或SVC（ARMv8）指令从用户态陷入内核，异常处理入口在arch/arm/kernel/entry-armv.S。
调用表映射：系统调用号通过arch/arm/kernel/sys_arm.c中的sys_call_table映射到具体处理函数，如sys_open对应do_sys_open。
典型ARM平台启动差异（函数级）
平台	关键函数差异
树莓派（RPi）	额外固件层函数：bootcode.bin调用start.elf中的initialize_platform()，再加载U-Boot。
ARM64（AArch64）	启动流程使用arch/arm64/kernel/head.S，MMU配置函数为__enable_mmu，支持4级页表。
嵌入式设备	可能自定义启动函数，如直接从NOR Flash加载内核，使用load_elf_image()替代U-Boot的do_bootm。
通过以上树状图，可清晰看到从硬件上电到应用程序的每一层函数调用关系，尤其适合系统开发人员调试启动问题、优化启动时间或开发定制化启动流程。如需进一步分析某模块的函数调用细节（如GIC中断初始化、USB驱动探测流程），可提供具体方向进行深入展开。
————————————————
版权声明：本文为CSDN博主「进击的程序汪」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
原文链接：https://blog.csdn.net/weixin_46356409/article/details/149063871
