# 特征化测试：{目标区域}

> 文件：`{文件路径}`
> 行范围：L{起始}-L{结束}
> C++ 标准：{CPP_STANDARD}
> 日期：{YYYY-MM-DD}

---

## 目的

特征化测试（Characterization Test）用于**锁定现有行为**，而非验证"正确性"。
在重构前写好特征化测试，确保重构不改变可观测行为。

参考：Michael Feathers《修改代码的艺术》第 13 章。

---

## 测试环境约束

- gtest 必须以 **C++14 或更高** 编译（gtest 内部使用 C++11 特性）
- 即使被测代码是 C++03 风格，测试文件本身用 C++14
- 编译命令示例：
  ```bash
  g++ -std=c++14 $(pkg-config --cflags gtest) \
      -o test_{name} test_{name}.cpp {被测文件}.cpp \
      $(pkg-config --libs gtest gtest_main) -pthread
  ```

---

## 测试设计

### 观测点

对目标区域确定需要锁定的观测点：

| # | 观测点 | 类型 | 输入 | 期望输出 |
|---|---|---|---|---|
| 1 | {函数名/行为} | {返回值/副作用/异常} | {具体输入} | {当前实际输出} |
| 2 | {函数名/行为} | {返回值/副作用/异常} | {具体输入} | {当前实际输出} |

### 接缝利用

为了让目标区域可测试，可能需要利用或创建接缝：

- **预处理接缝**：通过 `#define` 替换依赖
- **链接接缝**：通过链接不同的 `.o` 提供模拟实现
- **对象接缝**：通过继承/虚函数注入测试替身

### 全局变量处理

如果目标区域依赖全局变量：

```cpp
// 测试 fixture 中保存和恢复全局状态
class P{NNN}Test : public ::testing::Test {
protected:
    void SetUp() override {
        saved_global_x = g_global_x;
        // ... 保存所有相关全局变量
    }
    void TearDown() override {
        g_global_x = saved_global_x;
        // ... 恢复所有全局变量
    }
private:
    decltype(g_global_x) saved_global_x;
};
```

---

## 测试代码

```cpp
// test_characterize_P{NNN}.cpp
// 特征化测试 — 锁定 P-{NNN} 的现有行为
// 注意：这些测试记录的是"实际行为"，不是"期望行为"
//       如果测试失败，说明重构改变了语义

#include <gtest/gtest.h>
#include "{被测头文件}"

class CharacterizeP{NNN} : public ::testing::Test {
protected:
    void SetUp() override {
        // 初始化被测环境
    }
    void TearDown() override {
        // 恢复环境
    }
};

TEST_F(CharacterizeP{NNN}, {行为描述1}) {
    // Arrange: {设置前置条件}
    // Act: {执行被测行为}
    // Assert: {锁定当前输出}
    EXPECT_EQ({实际值}, {期望值});
}

TEST_F(CharacterizeP{NNN}, {行为描述2}) {
    // ...
}
```

---

## 编译与运行

```bash
# 编译
g++ -std=c++14 $(pkg-config --cflags gtest) \
    -o test_characterize_P{NNN} \
    test_characterize_P{NNN}.cpp {被测文件列表} \
    $(pkg-config --libs gtest gtest_main) -pthread

# 运行
./test_characterize_P{NNN} --gtest_output=xml:test_results_P{NNN}.xml

# 覆盖率（可选）
g++ -std=c++14 --coverage $(pkg-config --cflags gtest) \
    -o test_cov_P{NNN} \
    test_characterize_P{NNN}.cpp {被测文件列表} \
    $(pkg-config --libs gtest gtest_main) -pthread
./test_cov_P{NNN}
gcovr --filter '{被测文件}' --print-summary
```

---

## 检查清单

- [ ] 所有关键函数都有至少一个特征化测试
- [ ] 全局变量的 Setup/TearDown 正确保存恢复
- [ ] 测试通过（记录的是实际行为）
- [ ] 覆盖率报告已查看（无需 100%，但关键路径必须覆盖）
