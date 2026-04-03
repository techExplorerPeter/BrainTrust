### 互斥锁(Mutex) - ”会议室钥匙“
#### **核心思想**

	-	睡眠等待：获取不到锁时线程会主动让出CPU，进入睡眠状态，等待被唤醒。
#### **演进脉络**
	`**简单睡眠锁 -> 自适应自旋Mutex -> 乐观自旋Mutex**`
#### **底层原理精要**

	-	关键数据结构
   ```
        struct mutex {
        atomic_long_t owner;      // 锁所有者 + 状态标志
        spinlock_t wait_lock;     // 保护等待队列
        struct list_head wait_list; // 等待队列
	 };
   ```
	-	状态标志
	```
   #define MUTEX_FLAG_WAITERS   0x01  // 有等待者
    #define MUTEX_FLAG_HANDOFF   0x02  // 需要传递所有权
	 #define MUTEX_FLAG_PICKUP    0x04  // 正在传递所有权
	```
	-	加锁流程精髓
	```
   void mutex_lock(struct mutex *lock)
    {
        // 1. 快速路径：直接尝试获取
        if (__mutex_trylock_fast(lock))
	         return;

        // 2. 慢速路径
        __mutex_lock_slowpath(lock);
     }
       
    static noinline void __mutex_lock_slowpath(struct mutex *lock)
    {
        for (;;) {
            // 尝试乐观自旋
            if (__mutex_trylock_or_spin(lock, &waiter))
                 break;
       
            // 自旋失败，加入等待队列
             __mutex_add_waiter(lock, &waiter);
       
            // 设置进程状态为不可中断睡眠
             set_current_state(TASK_UNINTERRUPTIBLE);
       
            // 调度出去，让出CPU
            schedule_preempt_disabled();
        }
     }
    ```
    -	解锁流程精髓
    ```
   void mutex_unlock(struct mutex *lock)
    {
        // 释放锁
	     __mutex_unlock_fast(lock);

        // 如果有等待者，唤醒一个
        if (__mutex_has_waiters(lock))
            __mutex_wake_waiter(lock);
     }
    ```
#### **优化策略精髓**

	-	自适应自旋：
		-	如果锁持有正在其他CPU运行，短暂自旋等待
	-	如果锁持有者未运行，立即睡眠
	 -	乐观自旋：
		-	在加入等待队列前先自旋一段时间
	-	避免不必要的上下文切换开销
	-	等待队列优化
		-	使用FIFO队列保证公平性
		-	精确唤醒，避免"惊群效应"
#### **适用场景**

	-	临界区执行时间较长
	-	锁争用不激烈
	-	可以接受上下文切换开销

### 读写锁(rwlock) - "图书馆借阅规则"
#### **核心思想**

	-	读共享，写独占：允许多个读者并发访问，但写者需要独占访问

#### **演进脉络**
	`**读者优先 → 写者优先 → 公平读写锁**`

#### **底层原理精要**

	- 关键数据结构
	
	  ```
	  typedef struct {
	      arch_rwlock_t raw_lock;
	  } rwlock_t;
	  
	  // ARM64实现：32位计数器
	  // 高16位：写者计数 | 低16位：读者计数
	  ```
	-	读者加锁精髓
	```
   void read_lock(rwlock_t *lock)
    {
        // 原子增加读者计数
	     atomic_add(1, &lock->readers);

        // 如果有写者，等待
        while (atomic_read(&lock->writers)) {
            atomic_sub(1, &lock->readers);
            wait_for_writers();
            atomic_add(1, &lock->readers);
        }
     }
    ```
    -	写者加锁精髓
    ```
   void write_lock(rwlock_t *lock)
    {
        // 设置写者标志，阻止新读者
	     atomic_inc(&lock->writers);

        // 等待现有读者完成
        while (atomic_read(&lock->readers)) {
            cpu_relax();
         }
       
        // 现在获得独占访问
     }
    ```
#### **公平性策略精髓**

	-	读者优先策略
		-	新读者可以立即获得锁，即使有写者等待
	-	可能导致写者饥饿
	-	写者优先策略
		-	一旦有写者等待，新读者需要等待
		-	避免写者饥饿，但可能降低读并发性
	-	公平策略
		-	使用FIFO队列，按到达顺序服务
		-	读者和写者交替获得锁
#### **适用场景**

	-	读多写少的共享数据结构
	-	数据读取频繁但很少修改
	-	对数据一致性要求不是极端严格

### 信号量(Semaphore) - "停车场计数器"
#### 核心思想
	-	资源计数器：维护一个计数器，表示可用资源数量，支持P(获取)和V(释放)操作

#### 类型区分
	-	二进制信号量：计数器为0或1，类似互斥锁
	-	计数信号量：计数器大于1，控制资源池访问

#### 底层原理精要
	- 关键数据结构
	
	  ```
	  struct semaphore {
	      raw_spinlock_t lock;      // 保护计数器的自旋锁
	      unsigned int count;       // 可用资源数量
	      struct list_head wait_list; // 等待进程队列
	  };
	  ```
	
	-	P操作（获取）精髓
	
	  ```
	  void down(struct semaphore *sem)
	  {
	      unsigned long flags;
	      
	      raw_spin_lock_irqsave(&sem->lock, flags);
	      
	      if (likely(sem->count > 0)) {
	          // 有可用资源，直接获取
	          sem->count--;
	          raw_spin_unlock_irqrestore(&sem->lock, flags);
	          return;
	      }
	      
	      // 无可用资源，加入等待队列
	      __down(sem);
	  }
	  
	  static inline void __down(struct semaphore *sem)
	  {
	      DEFINE_WAIT(wait);
	      
	      for (;;) {
	          prepare_to_wait(&sem->wait_list, &wait, TASK_UNINTERRUPTIBLE);
	          
	          if (sem->count > 0)
	              break;
	              
	          schedule();  // 让出CPU
	      }
	      
	      finish_wait(&sem->wait_list, &wait);
	      sem->count--;  // 获得信号量
	  }
	  ```
	
	-	 V操作（释放）精髓
	
	  ```
	  void up(struct semaphore *sem)
	  {
	      unsigned long flags;
	      
	      raw_spin_lock_irqsave(&sem->lock, flags);
	      
	      if (list_empty(&sem->wait_list)) {
	          // 没有等待者，简单增加计数
	          sem->count++;
	      } else {
	          // 有等待者，唤醒一个
	          wake_up_one(&sem->wait_list);
	      }
	      
	      raw_spin_unlock_irqrestore(&sem->lock, flags);
	  }
	  ```
	
	-	特殊变种精髓
	
		-	完成量（Completion）
	
	      ```
	      struct completion {
	          unsigned int done;        // 完成状态
	          wait_queue_head_t wait;   // 等待队列
	      };
			
	      // 等待完成
	      void wait_for_completion(struct completion *comp)
	      {
	          if (!comp->done)
	              __wait_for_completion(comp);
	      }
			
	      // 通知完成  
	      void complete(struct completion *comp)
	      {
	          comp->done = 1;
	          wake_up_all(&comp->wait);
	      }
	      ```
			**精髓**：专门用于线程间”任务完成“通知，比信号量更轻量

#### 适用场景

	- 控制有限资源的并发访问数量
	- 生产者-消费者问题
	- 线程间同步和通信


### RCU（Read-Copy-Update） - ”无锁阅读，延迟回收“
#### 核心思想
	-	读无锁，写复制：读者不需要任何同步原语，写者通过复制-更新-延迟回收来保证一致性
#### 核心概念精髓
	-	宽限期（Grace Period）
		-	所有读者都离开临界区的时间点
		-	在此之后可以安全回收旧数据
	-	发布-订阅模式
	```
	// 写者更新
	new_data = kmalloc(sizeof(*new_data));
	memcpy(new_data, old_data, sizeof(*old_data));
	new_data->value = new_value;
	
	// 发布新数据（原子操作）
	rcu_assign_pointer(global_ptr, new_data);
	
	// 延迟回收旧数据
	call_rcu(&old_data->rcu_head, free_old_data);
	```
#### 底层原理精要
#### 读者操作
```
// 进入RCU读侧临界区
rcu_read_lock();

// 安全读取指针（内存屏障保证）
ptr = rcu_dereference(global_ptr);
// 使用ptr...

// 退出RCU读侧临界区
rcu_read_unlock();
```
##### 写者操作精髓
```
void update_data(new_value)
{
    // 1. 创建新版本
    new = kmalloc(sizeof(*new));
    *new = *old;  // 复制旧数据
    new->value = new_value;
    
    // 2. 原子替换（发布）
    rcu_assign_pointer(global_ptr, new);
    
    // 3. 等待宽限期后回收旧数据
    synchronize_rcu();
    kfree(old);
}
```
##### 内存屏障使用精髓
`rcu_assign_pointer()`
```
#define rcu_assign_pointer(p, v) \
    __rcu_assign_pointer((p), (v), __rcu)
    
#define __rcu_assign_pointer(p, v, space) \
    smp_store_release(&(p), (v))  // 写内存屏障
```
`rcu_dereference()`
```
#define rcu_dereference(p) \
    __rcu_dereference((p), __rcu)
    
#define __rcu_dereference(p, space) \
    smp_load_acquire(&(p))  // 读内存屏障
```
#### 适用场景
-	读多写少的数据结构
-	对读性能要求极高的场景
-	可以接受写操作开销较大

### 顺序锁（seqlock） - ”版本号检查“
#### 核心思想
	-	乐观读取：读者通过检查序列号来判断读取过程中数据是否被修改，如果被修改则重试
#### 底层原理精要

##### 关键数据结构

```
typedef struct {
    unsigned sequence;        // 序列号计数器
    spinlock_t lock;
} seqlock_t;
```



##### 读者操作精髓

```
unsigned read_begin(const seqlock_t *sl)
{
    // 读取序列号（无内存屏障）
    return READ_ONCE(sl->sequence);
}

int read_retry(const seqlock_t *sl, unsigned start)
{
    // 内存屏障，保证之前读取完成
    smp_rmb();
    
    // 检查序列号是否改变（奇数表示有写者）
    return (sl->sequence != start);
}

// 典型使用模式
do {
    seq = read_seqbegin(&seqlock);
    // 读取受保护的数据
    data1 = READ_ONCE(shared_data1);
    data2 = READ_ONCE(shared_data2);
} while (read_seqretry(&seqlock, seq));
```



##### 写者操作精髓

```
void write_seqlock(seqlock_t *sl)
{
    spin_lock(&sl->lock);
    
    // 序列号加1（变为奇数，表示正在写入）
    sl->sequence++;
    
    // 写内存屏障，保证序列号更新对其他CPU可见
    smp_wmb();
}

void write_sequnlock(seqlock_t *sl)
{
    // 写内存屏障，保证数据写入在序列号更新前完成
    smp_wmb();
    
    // 序列号加1（变为偶数，表示写入完成）
    sl->sequence++;
    
    spin_unlock(&sl->lock);
}
```



#### 序列号状态含义

- **偶数**：数据处于一致状态
- **奇数**：写者正在修改数据
- **序列号改变**：数据已被修改

#### 适用场景

- 读者远多于写者
- 数据结构简单，可以原子读取
- 读者可以容忍偶尔的重试

### 每CPU变量（Per-CPU Variables） - "各玩各的"

#### 核心思想

**数据本地化**：每个CPU有自己独立的数据副本，避免缓存行 bouncing。

#### 底层原理精要

##### 数据结构定义
```
// 定义每CPU变量
DEFINE_PER_CPU(int, my_counter);

// 动态分配
my_var = alloc_percpu(typeof(*my_var));
```

##### 操作精髓

```
// 获取当前CPU的变量指针
get_cpu_var(my_counter)++;  // 禁止抢占
put_cpu_var(my_counter);    // 恢复抢占

// 或者使用这个更安全的方式
this_cpu_inc(my_counter);   // 自动处理抢占

// 访问其他CPU的变量
per_cpu(my_counter, cpu_id) = value;
```

##### 统计汇总示例
```
unsigned long total_counter(void)
{
    unsigned long total = 0;
    int cpu;
    
    for_each_online_cpu(cpu) {
        total += per_cpu(my_counter, cpu);
    }
    return total;
}
```
#### 内存布局

```
CPU0副本 | CPU1副本 | CPU2副本 | ... | CPUn副本
```

每个副本位于不同的缓存行，避免伪共享。

#### 适用场景

- 计数器统计
- 临时缓冲区
- 不需要严格同步的每CPU数据

### spinlock核心精髓

-	**本质特征**

  -	忙等待：获取不到锁时CPU不会睡眠，而是循环检查
  -	轻量级：适合短期临界区保护
  -	不可睡眠：持有spinlock期间不能调用可能引起睡眠的函数

-	**演进脉络**
  `**原始spinlock(无序竞争) -> Ticket spinlock(公平排) -> MCS锁(本地自旋 ->Qspinlock(混合优化)**`

-	**各版本Spinlock底层原理精要**

  -	**1.原始spinlock**
  	
  	-	核心问题：无序竞争，不公平
  	```C
     // 简单原子操作
       ldrex [lock], tmp     // 独占加载
       teq tmp, #0          // 检查是否为0
  	  strexeq tmp, 1, [lock] // 尝试加锁
  	```
  	-	缺陷：多核竞争时，某些CPU因缓存位置优势总能抢到锁
   -	**2.Ticket Spinlock - 银行排队模式**
  	
  	-	核心思想：引入排队机制保证公平性
  	-	数据结构
  	```
      union {
           u32 slock;
           struct {
               u16 owner;    // 当前服务号
               u16 next;     // 下一个可取号
           } tickets;
       };
      ```
       -	加锁流程
       ```
       1: ldrex lockval, [lock]       ; 读取当前锁状态
          add newval, lockval, 0x10000 ; next++ (高16位+1)
          strex tmp, newval, [lock]    ; 尝试更新
          teq tmp, #0                 ; 更新成功?
          bne 1b                      ; 失败重试
      
          ; 等待叫号
          while (my_ticket != current_owner) {
              wfe();                  ; 低功耗等待
              current_owner = lock->owner ; 重新读取
          }
       ```
       -	精髓：
       	-	next：取号机，每个竞争者拿唯一号码
       	-	owner：取号器，严格按照顺序服务
       	-	WFE():等待时进入低功耗状态
       -	问题：释放锁时广播通知所有等待着，造成缓存一致性风暴
   -	**3.MCS锁 - 击鼓传花模式**
   	-	核心突破：将全局竞争转为本地等待
   	-	数据结构

   	```
   	struct mcs_spinlock {
   	     struct mcs_spinlock *next;  // 队列指针
   	     int locked;                 // 本地等待标志
   	 };
   	```
   	-	核心算法
   	```
   	// 加锁
   	 prev = xchg(lock, node);       // 加入队列尾部
   	 if (prev == NULL) return;      // 直接获得锁
   	 prev->next = node;             // 前驱指向我
   	 while (!node->locked)          // 本地自旋等待
   	     cpu_relax();
   	
   	 // 解锁  
   	 if (!node->next) {             // 我是最后一个
   	     if (cmpxchg(lock, node, NULL) == node)
   	         return;
   	     while (!node->next)        // 等待后继加入
   	         cpu_relax();
   	 }
   	 node->next->locked = 1;        // 传递锁给后继
   	```
   	-	精髓：
   		-	本地化自旋：每个CPU在自己的locked变量上自旋
   		-	链式通知：解锁时只通知直接后继，避免广播
   		-	无全局竞争：大幅减少缓存一致性流量
   	 -	缺陷：节点数据结构变大，无法直接替换现有spinlock
   -	**4.Qspinlock - 皇位继承模式**
   	-	核心创新：混合设计，兼容大小同时保证高性能
   	-	数据结构设计

   	```
   	struct qspinlock {
   	     union {
   	         atomic_t val;
   	         struct {
   	             u8  locked;    // 皇位(0-7bit)
   	             u8  pending;   // 太子位(8-15bit)  
   	             u16 tail;      // 队列尾(16-31bit)
   	         };
   	     };
   	 };
   	```
   	-	三级状态机
   		-	1.快速路径 - 直接上位
   		```
   		// 三元组: (tail, pending, locked)
   	     if (当前状态 == (0, 0, 0)) {
   	         locked = 1;  // 直接获得锁
   	         return;
   	     }
   	     ```
   	 	-	2.中速路径 - 太子候补
   	 	```
   	 	if (当前状态 == (*, 0, *)) {
   	         pending = 1;           // 抢占太子位
   	         wait_for(locked == 0); // 等皇位空出
   	         pending = 0; locked = 1; // 登基上位
   	         return;
   	     }
   	 	```
   	 	-	 3.慢速路径 - 藩王排队
   	 	```
   	 	// 需要MCS节点加入队列
   	     node = get_per_cpu_mcs_node();
   	     加入等待队列;
   	     自旋等待前驱传递;
   	     获得锁后处理后继;
   	 	```

-	**Spinlock设计精髓总结**

  -	**1.公平性演进**
  	-	原始；武力抢夺，强者恒强
  	-	Ticket：先来后到，绝对公平
  	-	MCS/Qspinlock:队列公平，高效公平
   -	**2.性能优化核心**
   	-	减少全局内存访问：从全局自旋 -> 本地自旋
   	-	降低缓存一致性流程： 从广播通知 -> 单播传递
   	-	功耗优化：从忙等待 -> WFE低功耗等待
   -	**3.数据结构智慧**
  	-	Ticket： 16+16bit巧妙编码，小空间大信息
  	-	Qspinlock：8+8+16bit精细化分，状态压缩极致
  	-	MCS：链表队列，逻辑清晰但空间稍大
   -	**4.原子操作艺术**
   	-	LDREX/STREX:ARM独占访问，实现无锁原子
   	-	内存屏障：保证指令顺序，避免乱序执行
   	-	缓存预取；提前加载，减少等待时间

-	**实际应用启示**

  -	短期保护用spinlock；临界区执行时间短时首选
  -	多核环境选新版：核数越多，Qspinlock优势越明显
  -	避免锁内睡眠：spinlock持有期间绝对不能调度
  -	关注锁争用：高争用场景考虑其他同步原语

### 同步原语选择决策树
```
是否需要同步？
    ↓
是 → 读者和写者比例如何？
        ↓
    读多写少 → 数据一致性要求？
            ↓
        严格 → RCU（如果写可接受延迟）
            ↓  
        宽松 → 顺序锁
        ↓
    写多或读写均衡 → 临界区执行时间？
            ↓
        短时间 → 自旋锁
            ↓
        长时间 → 互斥锁
    ↓
否 → 每CPU变量
```
### 性能特征总结

| 同步原语   | 读者开销 | 写者开销 | 公平性   | 适用场景     |
| :--------- | :------- | :------- | :------- | :----------- |
| **自旋锁** | 低       | 低       | 公平     | 短期临界区   |
| **互斥锁** | 中       | 中       | 公平     | 长期临界区   |
| **读写锁** | 很低     | 高       | 可配置   | 读多写少     |
| **RCU**    | 极低     | 很高     | N/A      | 读主导       |
| **顺序锁** | 极低     | 中       | 写者优先 | 简单数据结构 |
| **信号量** | 中       | 中       | 公平     | 资源池控制   |

每种同步原语都是特定场景下的最优解，理解其底层原理和适用条件，才能在性能与正确性之间做出最佳权衡。




### 1.引言（Spinlock详解）
通常我们说的**同步**其实有两个层面的意思：
	-	一个是线程的同步，主要是为了按照变成者指定的特定顺序执行
	-	另外一个是数据的同步，主要是为了保存数据
为了高效解决同步问题，前人抽象出同步原语供开发者使用。不仅多核，单核也需要同步原语，核心的问题是要保证共享资源访问的正确性。如果共享资源划分不合理，同步原语的开销会制约多核性能。
常见的同步原语有：互斥锁、条件变量、信号量、读写锁、RCU等。

本文主要聚焦于互斥锁，对应Linux的spinlock，我们试图沿着时间的脉络去梳理spinlock的不断改进的进程，如果涉及CPU体系结构，我们主要关注的是ARM体系结构的实现。后续如果有时间我们会继续分析其他同步原语的演进和优化历程。

### 2.演化进程
Linux内核Spinlock是互斥机制的最底层的基础设施，它的性能直接关系到内核的性能，主要分为这么几个阶段：
-	1.Linux-2.6.25之前，我们称之为**原始spinlock**。
	对锁的实现，是使用原子操作去无序竞争全局的锁资源
	这个阶段对锁的争用处于无序竞争的状态。如果CPU核心数不多，资源相对充裕，好比我们去银行柜台办理业务，一共就1-2个人，无非你在前还是我在前的问题，公平性的问题并不突出，性能也没什么大的影响，但是一旦cpu核心数和锁的竞争相对比较多的时候，就会出现有些人因为某些优势（如CPU算力强，锁正好落在当前CPU的cacheline中等）总是能抢到锁，其他人总是抢不到的情况出现。
-	2.Linux-2.6.25，在x86下实现了ticket spinlock，替换原始spinlock。
	随着CPU核心数的增多以及对共享资源的争用愈发的激烈，那么这时候公平性问题就显现出来了，保证公平一个很自然的思路就是大家都来排队。如果对锁的征用比较激烈再加上如果此时核比较多，此时一旦释放锁，其实只有1个CPU能抢到锁，但是因为大家观察都是全局的一个锁，那么其他CPU的cacheline就会因此失效，会有相当程序的性能损耗。还是就以去银行柜台办理业务为例，它的实现相当于去银行取号、排队、等叫号这么一个过程，问题在于叫号相当是一个广播机制，所有人都要侦听，还是有点浪费时间和精力。
-	3.Linux-3.5，ARM体系结构用ticket spinlock替换了原始spinlock
	过了几个版本，ARM才替换，原因我没有去考证，不得而知
-	4.Linux-3.15，实现了mcs_spinlock，但未替换ticket spinlock
	它把对全局锁转换成per-cpu的锁，减少争用的损耗，然后各个锁之间通过链表穿起来排队，解决了公平性和性能损耗的问题，然后它却没有替代ticket spinlock成为内核默认实现，因为spinlock太底层了，已经嵌入了内核的各种关键数据结构中，它的数据结构要比spinlock大，这是内核锁不能接受的，但是最终它还是合入了内核，只是没有人去使用它。但是它的存在为后一步的优化，仍然起到了非常重要的作用。它的实现思路是把ticket spinlock的广播机制转变为了击鼓传花，也就是实际上可以我并需要侦听广播，主要是在我前面排队的人在使用完锁以后告诉我就可以了。
-	5.Linux-4.2，实现了queued spinlock（简称qspinlock），替换了ticket spinlock
	它首先肯定要解决mcs_spinlock占用大小，实际上它结合了ticket spinlock和mcs_spinlock的有点，大小保持一致，如果只有1个或2个CPU试图获取锁，只用这个新的spinlock，当有3个以上的CPU试图获取锁，才需要mcs_spinlock。它的数据结构有表示当时锁的持有情况，是否有还有一个竞争者，已经需要快速找到对应CPU的per-cpu结构中mcs_spinlock节点，这3个大的域被塞在ticket spinlock同样大小的数据结构中。这种遵守原先架构约束的情况而做出的改进，非常值得我们去学习。
-	6.Linux-4.19,ARM体系结构将queue spinlock替换成默认实现。
	具体原因，没有去考证，也不得而知
	
### 3.原始spinlock实现
#### 3.1关键数据结构和公共代码
```
typedef struct {
	volatile unsigned int lock;
} raw_spinlock_t;

typedef struct {
	raw_spinlock_t raw_lock;
} spinlock_t;

#define spin_lock(lock)			_spin_lock(lock)

void __lockfunc _spin_lock(spinlock_t *lock)
{
	preempt_disable();
    _raw_spin_lock(lock);
}
# define _raw_spin_lock(lock)		__raw_spin_lock(&(lock)->raw_lock)
```
#### 3.2 ARM体系结构的加锁实现
```
//arm32（那时候还没arm64）的实现，这个时期的内核大体对应ARMV6
static inline void __raw_spin_lock(raw_spinlock_t *lock)
{
	unsigned long tmp;

	__asm__ __volatile__(
"1:	ldrex	%0, [%1]\n"      //1.
"	teq	%0, #0\n"            //2. 
"	strexeq	%0, %2, [%1]\n"  //3.
"	teqeq	%0, #0\n"        //4.
#ifdef CONFIG_CPU_32v6K
"	wfene\n"                 //5.
#endif
"	bne	1b"                  //6.
	: "=&r" (tmp)
	: "r" (&lock->lock), "r" (1) 
	: "cc");

	smp_mb();                //7.
}
```
通过数据结构，可以看出，此时的lock还是一个unsigned int类型的数据，加锁的时候，首先会关闭抢占，然后会跳转到各个体系结构的实现，我们关注ARM的实现，`__raw_spin_lock的分析如下`：
1.读取lock的状态值给tmp，并将&lock->lock标记为独占。
2.判断lock的状态是否为0，如果是0则说明可以继续往下走（跳到第3步）；如果不为0，说明自旋锁处于上锁状态，不能访问，跳到第5步（如果不支持WFE则直接跳到第6步）自旋最后回到第1步自旋。teq执行会影响标志寄存器中Z标志位，后面带eq或者ne后缀的执行都受该标志位影响。
3.执行`strex`执行，只有从上一次`strex`执行到本次`strex`这个被标记为独占的地址（&lock->lock）没有改变，才会执行成功（lock的状态改写为1）。通过`strex`执行和`ldrex`实现原子性操作。
4.继续判断lock的状态是否为0，为0说明获得锁；不为0说明没有获得锁，则跳到第5步（如果支持WFE的话）
5.执行`WE`指令（如果支持的话），cpu进入低功耗状态，省点功耗
6.如果收到`SEV`指令（如果有第5步的话），继续判断lock的状态是否为0，不为0则跳到第1步，继续循环；如果lock为0，继续跳到第7步
7.执行barrier（多核情况下为）`DMB`指令，保证访存顺序按我们的编程顺序执行（即后面的load/store绝不允许越过`smp_mb()屏障乱序到前面执行`）。
#### 3.3ARM体系结构的解锁实现
```
static inline void __raw_spin_unlock(raw_spinlock_t *lock)
{
	smp_mb();

	__asm__ __volatile__(
"	str	%1, [%0]\n"
#ifdef CONFIG_CPU_32v6K
"	mcr	p15, 0, %1, c7, c10, 4\n" /* DSB */
"	sev"
#endif
	:
	: "r" (&lock->lock), "r" (0)
	: "cc");
}
```
解锁的操作相对简单，str将lock—>lock赋值，然后使用DSB程序，使用seb通知持锁cpu得到锁。
### 4.ticket spinlock
#### 4.1关键数据结构和公共代码
```
typedef struct {
	union {
		u32 slock;
		struct __raw_tickets { //只考虑小端
			u16 owner;
			u16 next;
		} tickets;
	};
} arch_spinlock_t;

typedef struct raw_spinlock {
	arch_spinlock_t raw_lock;
} raw_spinlock_t;

typedef struct spinlock {
	union {
		struct raw_spinlock rlock;
	};
} spinlock_t;

static inline void spin_lock(spinlock_t *lock)
{
	raw_spin_lock(&lock->rlock);
}
#define raw_spin_lock(lock)	_raw_spin_lock(lock)
void __lockfunc _raw_spin_lock(raw_spinlock_t *lock)
{
	__raw_spin_lock(lock);
}
static inline void __raw_spin_lock(raw_spinlock_t *lock)
{
	preempt_disable();
	do_raw_spin_lock();
}
static inline void do_raw_spin_lock(raw_spinlock_t *lock) __acquires(lock)
{
	arch_spin_lock(&lock->raw_lock);
}
```
#### 4.2 AArch32的加锁实现
```
static inline void arch_spin_lock(arch_spinlock_t *lock)
{
	unsigned long tmp;
	u32 newval;
	arch_spinlock_t lockval;

	__asm__ __volatile__(
"1:	ldrex	%0, [%3]\n"          //1. 
"	add	%1, %0, %4\n"            //2.
"	strex	%2, %1, [%3]\n"      //3.
"	teq	%2, #0\n"                //4.
"	bne	1b"                      //5.
	: "=&r" (lockval), "=&r" (newval), "=&r" (tmp)
	: "r" (&lock->slock), "I" (1 << TICKET_SHIFT)
	: "cc");

	while (lockval.tickets.next != lockval.tickets.owner) {      //6.
		wfe();                                                   //7.
		lockval.tickets.owner = ACCESS_ONCE(lock->tickets.owner);//8.
	}

	smp_mb(); //9.
}
```

1.把lock->slock值保存到lock_val

2.newval = lockval + (1 << TICKET_SHIFT)= lockval + (1 << 16)，等价于newval =lockval.tickets.next++，相当于从银行取号机取号。

3.strex tmp, newval, [&lock->slock]，将新的值newval 存在lock中，strex将是否成功结果存入在tmp中

4.检查是否写入成功lockval.tickets.next

5.成功则跳到第6步，否则返回第1步重试，同上文类似也是实现原子操作

6.lockval.tickets.next和owner成员是否相等，相等跳到第9步，成功获得锁；没有则跳到第7步。成功的话，相当于银行柜台已经叫我的号了，我就可以去办理业务了，没有的话，我还要继续等。

7.执行`WFE`指令，CPU进低功耗状态，省点功耗。

8.如果收到`SEV`指令，从低功耗状态恢复，重新获得新的owner值，因为一般是别人释放了锁才会发送`SEV`指令，这时owner的值已经发生了变化，需要重新从内存中获取（ACCESS_ONCE本身的实现就是增加了volatile这个关键字，它确保编译器每次访问的变量都是从内存中获取，防止编译器优化）。

9.执行barrier，同上文描述，不再赘述。

#### 4.3 AArch32的解锁实现

```
static inline void arch_spin_unlock(arch_spinlock_t *lock)
{
	unsigned long tmp;
	u32 slock;

	smp_mb();

	__asm__ __volatile__(
"	mov	%1, #1\n"                //1. 
"1:	ldrex	%0, [%2]\n"          //2. 
"	uadd16	%0, %0, %1\n"        //3.
"	strex	%1, %0, [%2]\n"      //4.
"	teq	%1, #0\n"                //5.
"	bne	1b"                      //6.
	: "=&r" (slock), "=&r" (tmp)
	: "r" (&lock->slock)
	: "cc");

	dsb_sev();                   //7.
}
```

1. 将tmp赋值为1
2. 将lock->slock的值赋值给slock。
3. 将slock的低16bit，也就是owner成员的值加1。
4. 将新的值新的ower，使用`strex`写入中`lock->slock`，将是否成功结果存入在tmp中
5. 检查是否写入成功，成功，跳到第7步，实现了原子操作；不成功跳到第6步；
6. tmp不等于0（不成功），继续返回`label 1`重试，即跳回第2步

#### 4.4 AArch64的加锁实现

```
static inline void arch_spin_lock(arch_spinlock_t *lock)
{
	unsigned int tmp;
	arch_spinlock_t lockval, newval;

	asm volatile(
"	prfm	pstl1strm, %3\n"       //1.
"1:	ldaxr	%w0, %3\n"             //2.
"	add	%w1, %w0, %w5\n"           //3.
"	stxr	%w2, %w1, %3\n"        //4.
"	cbnz	%w2, 1b\n"             //5.
	/* Did we get the lock? */
"	eor	%w1, %w0, %w0, ror #16\n"  //6.
"	cbz	%w1, 3f\n"                 //7.
"	sevl\n"                        //8.
"2:	wfe\n"                         //9.
"	ldaxrh	%w2, %4\n"             //10.
"	eor	%w1, %w2, %w0, lsr #16\n"  //11.
"	cbnz	%w1, 2b\n"             //12.
"3:"                               //13.
	: "=&r" (lockval), "=&r" (newval), "=&r" (tmp), "+Q" (*lock)
	: "Q" (lock->owner), "I" (1 << TICKET_SHIFT)
	: "memory");
}
```

核心逻辑与AArch32类似，汇编实现会有不一样，这里不再展开。

1. 从lock（memory）预取数据到L1cache中，加速执行。
2. 使用`ldaxr`指令（Load-acquire exclusive register，带Exclusive和Acquire-Release 两种语义），将lock的值赋值给lockval。
3. newval = lockval + (1 << TICKET_SHIFT)= lockval + (1 << 16)，等价于newval =lockval.tickets.next++，相当于从银行取号机取号。
4. 使用`stxr`指令，将newval赋值给lock，并将exclusive是否设置成功结果存放到tmp中。
5. 如果tmp != 0，说明exclusive失败，需要重新跳到开始处（第2步）重试，因为这时候其他CPU核心可能有是执行流插入，抢在我们前面执行。否则继续。
6. 用`eor 异或运算`实现lockval.tickets.next和owner成员是否相等的判断
7. 如果相等，跳到`label`3（对应13步），获得锁进入临界区。否则往下，执行自旋。
8. 使用`SEVL`指令（发送本地事件，Send Event Locally），唤醒本CPU核心，防止有丢失unlock的情况出现。
9. 执行`WFE`指令，CPU进低功耗状态，省点功耗。
10. 获取当前的Owner值存放在tmp中
11. 判断lockval.tickets.next和owner成员的值是否相等
12. 如果不相等就回跳到`label`2（对应第9步）。相等继续往下。
13. 结束退出。

#### 4.5 AArch64的解锁实现

```
static inline void arch_spin_unlock(arch_spinlock_t *lock)
{
    asm volatile(
"   stlrh   %w1, %0\n"
    : "=Q" (lock->owner)
    : "r" (lock->owner + 1)
    : "memory");
}
```

解锁的操作相对简单，`stlrh`除了将lock->owner++（相当于银行柜台叫下一个排队者的号码），将会兼有`SEV`和`DSB`的功能。

### 5. mcs spinlock

#### 5.1 关键数据结构和变量

```
struct mcs_spinlock {  struct mcs_spinlock *next; //1.  in``t nt locked;                //2.};
```

1. 当一个CPU试图获取一个spinlock时，它就会将自己的MCS lock加到这个spinlock的等待队列的队尾，然后`next`指向这个新的MCS lock。
2. `locked`的值为1表示已经获得spinlock，为0则表示还没有持有该锁。

#### 5.2 加锁的实现

```
static inline void mcs_spin_lock(struct mcs_spinlock **lock, struct mcs_spinlock *node)
{
	struct mcs_spinlock *prev;
 
	node->locked = 0;               //1.
	node->next   = NULL;

	prev = xchg(lock, node);        //2
	if (likely(prev == NULL)) {     //3
		return;
	}
	ACCESS_ONCE(prev->next) = node; //4

	arch_mcs_spin_lock_contended(&node->locked); //5.
}
```

先看下两个参数：

- 第1个参数`lock`：是指向指针的指针（二级指针），是因为它指向的是末尾节点里的`next`域，而`next`本身是一个指向`struct mcs_spinlock`的指针。
- 第2个参数`node`：试图加锁的CPU对应的MCS lock节点。

接下来看代码逻辑

1. 初始化node节点

2. 找队列末尾的那个mcs lock。`xchg`完成两件事，一是给一个指针赋值，二是获取了这个指针在赋值前的值，相当于下面两句：

   ```
   prev = *lock; //队尾的lock
   *lock = node; //将lock指向新的node
   ```

3. 如果队列为空，CPU可以立即获得锁，直接返回；否则继续往下。不需要基于"locked"的值进行spin，所以此时`locked`的值不需要关心。

4. 等价于`prev->next = node`，把自己这个`node`加入等待队列的末尾。

5. 调用`arch_mcs_spin_lock_contended`，等待当前锁的持有者将锁释放给我。

```
#define arch_mcs_spin_lock_contended(l)	 \
do {									 \
	while (!(smp_load_acquire(l)))		 \ //1. 
		arch_mutex_cpu_relax();			 \ //2.
} while (0)
```

1. 上文中的`node->locked`==0，说明没有获得锁，需要继续往下执行；说明已经获得锁，直接退出
2. ARM64中`arch_mutex_cpu_relax`调用`cpu_relax`函数的，有一个内存屏障指令防止编译器优化。从4.1开始还存一个`yield`指令。该指令，为了提高性能，占用cpu的线程可以使用该给其他线程。

#### 5.3 解锁的实现

```
static inline void mcs_spin_unlock(struct mcs_spinlock **lock, struct mcs_spinlock *node)
{
	struct mcs_spinlock *next = ACCESS_ONCE(node->next); //1.

	if (likely(!next)) {                                 //2.
		if (likely(cmpxchg(lock, node, NULL) == node))   //3
			return;
		while (!(next = ACCESS_ONCE(node->next)))        //4.
			arch_mutex_cpu_relax();                      //5.
	}

	arch_mcs_spin_unlock_contended(&next->locked);       //6.
}
```

1. 找到等待队列中的下一个节点

2. 当前没有其他CPU试图获得锁

3. 直接释放锁。如果`*lock == node`，将`*lock = NULL`，然后直接返回；反之，说明当前队列中有等待获取锁的CPU。继续往下。`cmpxchg`作用翻译大致如下所示：

   ```
   cmpxchg(lock, node, NULL)
   {
   	ret = *lock;
   	if (*lock == node)
   		*lock = NULL;
   	return ret;
   }
   ```

4. 距离函数开头获得"next"指针的值已经过去一段时间了，在这个时间间隔里，可能又有CPU把自己添加到队列里来了。需要重新获得next指针的值。于是，待新的node添加成功后，才可以通过arch_mcs_spin_unlock_contended()将spinlock传给下一个CPU

5. 如果next为空，调用`arch_mutex_cpu_relax`，作用同上文。

6. arch_mcs_spin_unlock_contended(l)，实际上是调用smp_store_release((l), 1)，将next->locked设置为1。将spinlock传给下一个CPU

### 6. queued spinlock

#### 6.1 概述

它首先肯定要解决`mcs_spinlock`的占用空间问题，否则设计再好，也无法合入主线。它是这样的：大部分情况用的锁大小控制在跟以前`ticket spinlock`一样的水平，设计了两个域：分别是`locked`和`pending`，分别表示锁当前是否被持有，已经在持有时，是否又来了一个申请者竞争。争锁好比抢皇位，皇位永远只有1个（对应`locked`域），除此之外还有1个太子位（对应`pending`域），防止皇帝出现意外能随时候补上，不至于出现群龙无首的状态，他们可以住在紫禁城内（使用`qspinlock`）。这两个位置被占后，其他人还想来竞争皇位，只有等皇帝和太子都移交各自的位子以后才可以，在等待的时候你需要在紫禁城外待在自己的府邸里（使用`mcs_spinlock`），减小紫禁城的拥挤（减少系统损耗）。

即当锁的申请者小于或等于2时，只需要1个`qspinlock`就可以了，其所占内存的大小和`ticket spinlock`一样。当锁的竞争者大于2个时候，才需要(N-2)个`mcs_spinlock`。`qspinlock`还是全局的，为降低锁的竞争，使用退化到per-cpu的`mcs_spinlock`锁，所有的`mcs_spinlock`锁串行构成一个等待队列，这样cacheline invalide带来的损耗减轻了很多。这是它的基本设计思想。

在大多数情况下，per-cpu的`mcs lock`只有1个，除非发生了嵌套task上下文被中断抢占，因为中断上下文只有3种类（softirq、hardirq和nmi），所有每个CPU核心至多有4个`mcs_spinlock`锁竞争。而且，所有`mcs_spinlock`会串联到一个等待队列里的。

![](.\image\cpuf11.png)

上图展示的是：`qspinlock`的`locked`和`pending`位都被占，需要进入`mcs_spinlock`等待队列，而CPU(2)是第1个进入等待队列的，`qspinlock`的`tail.cpu`则被赋值成2，CPU(2)的`mcs_spinlock`数组的第3个成员空闲，则`qspinlock`的`tail.index`被赋值成3。入队的是CPU(3)、CPU(1)和CPU(0)，通过`mcs_spinlock`的`next`域将大家连成队列。

假如等到竞争`qspinlock`的2个锁的持有者，都释放了，则CPU(2)的第3个空闲成员则获得锁，完成它的临界区访问后，通过`qspinlock`的`tail.cpu`（类似于页表基址）和`tail.index`（类似于页表内的偏移），快速找到下个`mcs_spinlock`的node节点。

下面要进入细节分析了，本文只考虑小端模式、NR_CPUS < 16K的情况，不考虑虚拟化这块，去掉qstats统计，力图聚焦在该锁实现的核心逻辑上。

#### 6.2 关键数据结构和变量

##### struct qspinlock



数据简化如下：

```
typedef struct qspinlock {
    union {
        atomic_t val;
        struct {
            u8	locked;
            u8	pending;
        };
        struct {
            u16	locked_pending;
            u16	tail;
        };
    };
} arch_spinlock_t;
```

`struct qspinlock`包含了三个主要部分：

1. `locked`（0- 7bit）：表示是否持有锁，只有1和0两个值，1表示某个CPU已经持有锁，0则表示没有持有锁。
2. `pending`(8bit)：作为竞争锁的第一候补，第1个等待自旋锁的CPU只需要简单地设置它为1，则表示它成为第一候补，后面再有CPU来竞争锁，则需要创建mcs lock节点了；为0则表示该候补位置是空闲的。
3. `tail`(16-31bit): 通过这个域可以找到自旋锁队列的最后一个节点。又细分为：
   - `tail cpu`(18-31bit)：来记录和快速索引需要访问的`mcs_spinlock`位于哪个CPU上，作用类似于页表基址。
   - `tail index`(16-17bit)：用来标识当前处在哪种context中。Linux中一共有4种context，分别是task, softirq, hardirq和nmi，1个CPU在1种context下，至多试图获取一个spinlock，1个CPU至多同时试图获取4个spinlock。当然也表示嵌套的层数。对应per-cpu的`mcs_spinlock`的数组（对应下文的`struct mcs_spinlock mcs_nodes[4]`）的下标，作用类似于类似于页表内的偏移。

##### struct mcs_spinlock

`mcs_spinlock`的数据结构如下：

```
struct mcs_spinlock {
	struct mcs_spinlock *next;
	int locked; /* 1 if lock acquired */
	int count;  /* nesting count, see qspinlock.c */
};

struct qnode {
	struct mcs_spinlock mcs;
};

static DEFINE_PER_CPU_ALIGNED(struct mcs_spinlock, mcs_nodes[4]);
```

使用per-cpu的`struct mcs_spinlock mcs_nodes[4]`，可以用来减少对cacheline的竞争。数组数量为4前文已经解释过了。`struct mcs_spinlock`具体含义如下：

1. `locked`：用来通知这个CPU你可以持锁了，通过该域完成击鼓传花，当然这个动作是上一个申请者释放的时候通知的。
2. `count`：嵌套的计数。只有第0个节点这个域才有用，用来索引空闲节点的。
3. `next`：指向下一个锁的申请者，构成串行的等待队列的链表。

#### 6.3 加锁实现

##### 核心逻辑概述

我们把一个qspinlock对应的**( tail, pending, locked)称为一个三元组(x,y,z)**，以此描述锁状态及其迁移，有2中特殊状态：

1. 初始状态（无申请者竞争）：(0, 0, 0)
2. 过渡状态（类似于皇帝正在传位给太子，处于交接期）：(0, 1, 0)

按加锁原有代码只有慢速路径和非慢速路径，我们为了行文方便，将源代码的慢速路径又分为中速路径和慢速路径，这样就有以下三组状态：

| 不同路径 | 出现情况                                      | 核心功能所在的函数和使用锁的种类              |
| -------- | --------------------------------------------- | --------------------------------------------- |
| 快速路径 | 锁没有持有者，`locked`位（皇位）空缺          | queued_spin_lock，使用`qspinlock`             |
| 中速路径 | 锁已经被持有，但`pending`位（太子位）空缺     | queued_spin_lock_slowpath，使用`qspinlock`    |
| 慢速路径 | 锁已经被持有，`locked`位和`pending`位都没空缺 | queued_spin_lock_slowpath，使用`mcs_spinlock` |

核心逻辑就变成：

1. 如果没有人持有锁，那我们进入快速路径，直接拿到锁走人，走之前把`locked`位（皇位）标记成已抢占状态。期间，只需要使用`qspinlock`。
2. 如果有人持有锁（抢到了皇位成为皇帝），但`pending`位（太子位）空缺，那我们先抢这个位置，进入的是中速路径，等这个人（皇帝）释放锁（传位）了，我们就可以拿到锁了。期间，只需要用到`qspinlock`。
3. 如果这两个位置我们都抢不到，则进入慢速路径，需要使用per-cpu的`mcs_spinlock`。

总体状态流程图如下：

![](.\image\cpuf12.png)

梳理一下对应伪码描述：

```
static __always_inline void queued_spin_lock(struct qspinlock *lock)
{
    if (初始状态){ //没人持锁
        //进入快速路径
  return;}
 queued_spin_lock_slowpath(lock, val); //进入中速或者慢速路径
}

void queued_spin_lock_slowpath(struct qspinlock *lock, u32 val) //lock是原始锁，val是之前拿到的lock->val的值
{
    //代码片段1：过渡状态判断：看是否处于过渡状态，尝试等这个状态完成
    //代码片段2：慢速路径判断：看是否有其他申请者竞争，则直接进入慢速路径的核心片段
    //代码片段3：中速路径

queue: 
    //代码判断4：慢速路径
    //1. 调用__this_cpu_inc(mcs_nodes[0].count)将当前cpu竞争锁的数量+1
    //2. mcs node的寻址和初始化
    //3. 调用queued_spin_trylock(),看看准备期间spinlock是不是已经被释放了
    //4. 处理等待队列已经有人的情况，重点是arch_mcs_spin_lock_contended();
    //5. 处理我们加入队列就是队首的情况
locked:// 已经等到锁了
    //6.处理我们是队列最后一个节点的情况
    //7.处理我们前面还有节点的情况
    //8.调用arch_mcs_spin_unlock_contended()通知下一个节点
release:
    //9.__this_cpu_dec(mcs_nodes[0].count);
}
```

下面我们开始分析

`queued_spin_lock`和`queued_spin_lock_slowpath`函数的实现细节。

##### 实现细节分析

```
static __always_inline void queued_spin_lock(struct qspinlock *lock)
{
	u32 val;

	val = atomic_cmpxchg_acquire(&lock->val, 0, _Q_LOCKED_VAL); //1
	if (likely(val == 0))                                       //2
		return;
	queued_spin_lock_slowpath(lock, val);                       //3
}
```

1. 通过`atomic_cmpxchg_acquire`，与之前的`cmpxchg`类似，用原子操作实现：
   - 将val赋值为lock->val。
   - lock->val值如果为0（没人拿到锁），将lock->val的值设为1(即*_Q_LOCKED_VAL*)，三元组状态由**( tail, pending, locked)**= (0, 0, 0)迁移为(0, 0, 1)。
   - lock->val值如果不为0，保持lock->val的值不变。
2. 如果当前没有人获得锁，直接拿到锁返回。三元组的状态迁移已经在上一步完成了。否则需要继续往下，走中速/慢速路径。
3. 进入中速/慢速路径，调用`queued_spin_lock_slowpath`函数

##### 快速路径

lock->val值==0（没人拿到锁），三元组状态由**( tail, pending, locked)**= (0, 0, 0)迁移为(0, 0, 1)。快速返回，不用等待。

下面进入`queued_spin_lock_slowpath`函数的分析，我们先分析过渡状态判断和中速路径两个代码片段：

```
void queued_spin_lock_slowpath(struct qspinlock *lock, u32 val)
{

    /* 过渡状态判断 */
	if (val == _Q_PENDING_VAL) {                                          //0.    
		int cnt = _Q_PENDING_LOOPS;
		val = atomic_cond_read_relaxed(&lock->val,(VAL != _Q_PENDING_VAL) || !cnt--);
	}
    /*其他部分代码*/

}
```

##### 过渡状态判断

1. 如果三元组( tail,pending,locked)状态如果是(0, 1, 0)，则尝试等待状态变为 (0, 0, 1)，但是只会循环等待1次。

   简单翻译一下`atomic_cond_read_relaxed`语句的意思为：如果(lock->val != _Q_PENDING_VAL) || !cnt--)则跳出循环，继续往下。

##### 中速路径

![](.\image\cpu13.png)

进入中速路径的前提是当前没有其他竞争者在等待队列中排队以及`pending`位空缺，之后我们先将`pending`位占住。如果已经这段期间已经有人释放了，那直接获取锁并将`pending`位重置为空闲，反正则要自旋等持锁者释放锁再做其他动作。

```
void queued_spin_lock_slowpath(struct qspinlock *lock, u32 val)
{

    /* ... 过渡状态判断及处理，代码省略 */

    /* ... 判断是否有pending和tail是否有竞争者，有竞争者直接进入慢速路径排队，代码省略 */
    
    /* 中速路径开始 */
    val = atomic_fetch_or_acquire(_Q_PENDING_VAL, &lock->val);             //1. 
    if (!(val & ~_Q_LOCKED_MASK)) {                                        //2.
        if (val & _Q_LOCKED_MASK) {                                        //3.
            atomic_cond_read_acquire(&lock->val, !(VAL & _Q_LOCKED_MASK)); //4.
        }

        clear_pending_set_locked(lock);                                    //5.
        return;                                                            //6.
    }
    
    if (!(val & _Q_PENDING_MASK))                                          //7.
        clear_pending(lock);
    /* 中速路径结束 */

    /*其他部分代码*/

}
```

这部分代码的核心逻辑是在竞争`qspinloc`的`pending`，即竞争太子位。进入中速路径的前提是三元组( tail,pending,locked)=(0, 0, *)

1. 离“是否是过渡状态”和“除锁的持有者者之外是否竞争者”的判断已经过了一段时间了。需要用`atomic_fetch_or_acquire`函数，通过原子操作，重新看一下锁的状态，执行了两个动作：

   执行完，三元组状态会从(0, 0, *)改为(0, 1, *)。

   - val = lock->val（成为“原始的lock->val”）
   - lock->val的`peding`域被置位。

2. 如果原始的`lock->val`的`pending`和`tail`域都为0，则表明没有`pending`位没有其他竞争者，即太子位空闲可以去竞争；否则，则表明有其他竞争者，不满足中速路径的条件，需要进入慢速路径。`lock->val`的和`tail`域就不用关心了。所以此时的三元状态可以使(*, 1, *)

3. 如果`locked`域为1，表明位置被占着，已经有人在持锁了，我们需要跳到第4步，等锁被释放；否则，没有人持锁，皇位是空着的，我们跳到第5步，直接去上位就好了。

4. spin等待，直到`lock->val`的`locked`域变回0，也就是等皇位空出来。三元组状态会从(*, 1, 1) 转变为( *, 1, 0)

5. 拿到锁了，可以登基上位了，但还要做些清理工作，调用`clear_pending_set_locked`，将`lock->val`的`pending`域清零以及将`locked`置1。即三元组状态由(*, 1, 0) 转变为( *, 0, 1)。

6. 结束，提前返回。

7. 如果没有进入中速路径，第1步开始时获得的锁的状态是(n, 0, *) ，需要把在第一步设置的现在锁的`pending`域恢复成0。

##### 慢速路径

![](.\image\cpuf13.png)

上面流程图有些地方不太准确，但没有关系，可以先帮我们建立起总体流程印象，细节后续我们会展开。

在拿到`mcs lock`的空闲节点之后，我们先用`queued_spin_trylock`函数，检查一下在我们准备的这段时间里，是不是已经有人释放了该锁了，如果有人释放了，就提前返回了。

获得锁之前，要分两种情况分别处理：

- 如果队列中只有我们，那只用自旋等lock的`pending`位空出来即可。
- 如果队列中还有其他竞争者在排在我们前面，则需要自旋等前序节点释放该锁。

获得锁之后，也要分两种情况处理：

- 如果队列中只有我们，将锁的`locked`位置位，表明锁已经被我们持有了，不需要再做其他处理。
- 如果队列中还有其他竞争者在排在我们后面，则需要将锁传递这位竞争者，当然需要要等它正式加入。

慢速路径的简化代码如下所示：

```
void queued_spin_lock_slowpath(struct qspinlock *lock, u32 val)
{
	struct mcs_spinlock *prev, *next, *node;
	u32 old, tail;
	int idx;

    /* ... 过渡状态判断及处理，省略 */

    /* 先判断是否有pending和tail是否有竞争者，有竞争者直接进入慢速路径排队 */
    if (val & ~_Q_LOCKED_MASK)
        goto queue;

    /* 中速路径代码开始 */
	val = atomic_fetch_or_acquire(_Q_PENDING_VAL, &lock->val);
    if (!(val & ~_Q_LOCKED_MASK)) {
        // ...中速路径处理，省略
        return;
    }
    /* 中速路径代码结束 */

    /* 之前代码的收尾清理工作 */
	if (!(val & _Q_PENDING_MASK))
		clear_pending(lock); //将pending状态恢复。


    //慢速路径代码开始位置
queue://进入mcs lock队列
	node = this_cpu_ptr(&mcs_nodes[0]);                            //1.
	idx = node->count++;
	tail = encode_tail(smp_processor_id(), idx);

	node += idx;                                                   //2.
	barrier();
	node->locked = 0;
	node->next = NULL;

	if (queued_spin_trylock(lock))                                 //3.
		goto release;
	smp_wmb();

	old = xchg_tail(lock, tail);                                   //4.
	next = NULL;

	if (old & _Q_TAIL_MASK) {                                      //5.
		prev = decode_tail(old);                                   //6.
		WRITE_ONCE(prev->next, node);                              //7.
		arch_mcs_spin_lock_contended(&node->locked);               //8.
		next = READ_ONCE(node->next);                              //9.
		if (next)
			prefetchw(next);
	}

	val = atomic_cond_read_acquire(&lock->val, !(VAL & _Q_LOCKED_PENDING_MASK)); //10.

locked: 
	if (((val & _Q_TAIL_MASK) == tail) &&                            //11.
        atomic_try_cmpxchg_relaxed(&lock->val, &val, _Q_LOCKED_VAL))
		goto release; /* No contention */

	set_locked(lock);                                                //12.

	if (!next)                                                       //13.
		next = smp_cond_load_relaxed(&node->next, (VAL));

	arch_mcs_spin_unlock_contended(&next->locked);                   //14.

release:
	__this_cpu_dec(mcs_nodes[0].count);                              //15.
}
```

之前是进入`queued_spin_lock_slowpath`函数，有“是否过渡状态的判断”及处理，“是否要进入慢速路径的判断”及处理，如果进了中速路径的处理。下面正式进入慢速路径的处理。因为系统可能有多个cpu并发，即使在同一个cpu上也可能切换了4种context上下文的中一种，说不定大家竞争的锁已经都被释放了也说不准，所以此时三元组的状态是未知的。

1. 获得local CPU上的第0个节点`mcs_spinlock`类型的node节点，并将节点的count值+1，count值记录了local CPU上空闲节点的起始下标，该值也只在第0个有意义。`encode_tail`函数，节点编号编码成tail(2bit的tail index和14bit的tail cpu)，同时还完成：

   - 区分到底是tail域没有指向任何节点，还是指向了第0个CPU的第0个节点。
   - 检查当前CPU上自旋锁嵌套的层数是否超过4层。

2. 根据idx取到取到空闲节点，相当于node = mcs_nodes[idx]。这里有`barrier`保序，防止编译器优化。然后对空闲节点进行初始化。

3. 调用`queued_spin_trylock`函数，检查一下在我们准备的这段时间里，是不是已经有人释放了该锁了。如果成功获得锁，则直接跳到`lable release`处；否则，继续往下。`queued_spin_trylock`函数的作用具体来讲是这样：

   连续两次使用原子操作检查锁的状态：如果val为0（对应三元组(0, 0, 0)）并且再次读取val的`locked`域也为0，则表示可以获得锁。上文说过，此时锁的状态是未知的。

4. 在调用`xchg_tail`函数之前，有`smp_wmb`内存屏障，保证tail值获得的正确性。该函数将`lock->tail`设置为新生成的tail值，并将旧的值存在old中。

5. 如果旧的tail为0，说明队列里只有我们这个新生成的节点，直接跳到第10步；否则继续往下执行

6. 通过旧的tail拿到等待队列的尾结点`prev`。

7. 将当前节点插入等待队列，作为新的尾节点。

8. 自旋等待本节点的`locked`域变为1。在local CPU上自旋等待自己的locked成员被置位。`arch_mcs_spin_lock_contended`在arm64上最终会调用`__cmpwait_case_##name`宏，展开后同arm64的tick spinlock的`arch_spin_lock`的实现类似。核心功能都是在自旋时执行`WFE`节省部分能耗。

9. 后面3行代码，是看下在我们后面是否还有其他人在排队，如果有的话，使用`prfm`指令，提前将相关值预取到local CPU的cache中，加速后续的执行。

10. 使用原子操作重新获取`lock->val`的值，并且循环等到直到`pending`和`locked`都为0。三元组( tail, pending, locked)的值为(*, 0, 0)，也就是说需要等到皇位和太子位都是空闲的状态才是我们真正获得了锁的条件。

11. 如果tail还是我们设置的，说明我们同时是等待队列的最后一个节点或者说是唯一节点，后面没人在排队了。通过`atomic_try_cmpxchg_relaxed`原子的将`locked`域设置为1，至此才真正完成了锁的合法拥有，直接跳到最后1步。三元组的状态迁移是(n, 0, 0) --> (0, 0, 1)。否则，如果tail发生了改变，说明后面还有节点或者`pending`位被占，则继续往下处理。

12. 先将`locked`设置为1。三元组的状态迁移是(*, *, 0) --> (*, 0, 1)。

13. 等待的下一个节点还有正式加入进来，则需要等next变成非空（非空才真正了完成加入）。

14. 调用`arch_mcs_spin_unlock_contended`，将下一个节点的locked值设置成1 ，完成了锁的传递。也就是完成了击鼓传花。

15. 释放本节点。

#### 6.4 解锁实现

```
static __always_inline void queued_spin_unlock(struct qspinlock *lock)
{
	smp_store_release(&lock->locked, 0);
}
```

将`qspinlock`的`locked`清零即可。



#### **【参考资料】**

1. **【原创】linux spinlock/rwlock/seqlock原理剖析（基于ARM64）**

2. **宋宝华：几个人一起抢spinlock，到底谁先抢到？**

3. **Linux内核同步机制之（四）：spin lock，蜗窝科技**
4. **Linux中的spinlock机制[一] - CAS和ticket spinlock，兰新宇，知乎**