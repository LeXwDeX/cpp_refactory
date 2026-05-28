// legacy_monster.cpp — 模拟真实遗留代码屎山
//
// 刻意包含所有典型的"屎山反模式"，用于 E2E 重构测试：
//   - God function（200+ 行，圈复杂度 >20）
//   - 危险全局变量（SIOF 风险，动态初始化）
//   - 深层虚继承（钻石问题）
//   - 宏丛林（嵌套 #ifdef 4+ 层）
//   - 过度使用 const_cast / reinterpret_cast
//   - 资源泄漏（裸 new，无 RAII）
//   - 平台相关代码混在业务逻辑中
//
// 不是合法可编译代码——但 libclang 能解析它得出 AST。

#include <string>
#include <vector>
#include <memory>
#include <cstring>
#include <cstdlib>
#include <iostream>

// ============================================================
// 全局变量丛林 — SIOF 风险区
// ============================================================
extern int g_global_counter;                        // extern, 跨 TU
static std::string g_log_prefix = "LEGACY";         // file_static, 动态初始化!
static int g_retry_count = 3;                       // file_static, POD

namespace {
    std::vector<std::string> g_error_history;       // anon_ns, 动态初始化!
    int g_anon_flag = 0;                            // anon_ns, POD
    const int g_magic_number = 0xDEADBEEF;          // anon_ns, const
}

namespace legacy {
namespace internal {
    int g_deep_counter = 0;                          // extern (named ns)
    static int g_internal_flag = 1;                  // file_static
}
}

// ============================================================
// 深层继承 + 虚菱形（钻石问题）
// ============================================================
class ISerializable {
public:
    virtual ~ISerializable() {}
    virtual std::string Serialize() const = 0;
    virtual bool Deserialize(const std::string& data) = 0;
};

class ILoggable {
public:
    virtual ~ILoggable() {}
    virtual void LogState() const = 0;
};

class BaseComponent : public ISerializable, public ILoggable {
public:
    BaseComponent() : id_(0), name_("unnamed") {}
    virtual ~BaseComponent() {}

    virtual int GetId() const { return id_; }
    virtual void SetId(int id) { id_ = id; }
    virtual void Process(int input) { last_result_ = input; }
    virtual int GetResult() const { return last_result_; }

    std::string Serialize() const override { return name_; }
    bool Deserialize(const std::string& data) override { name_ = data; return true; }
    void LogState() const override {}

    static int s_instance_count;

protected:
    int id_;
    std::string name_;
    int last_result_ = 0;
};

int BaseComponent::s_instance_count = 0;             // class_static

class NetworkComponent : public virtual BaseComponent {
public:
    NetworkComponent() : port_(8080), connected_(false) {}
    virtual ~NetworkComponent() {}

    virtual bool Connect(const std::string& host, int port) {
        host_ = host;
        port_ = port;
        connected_ = true;
        return true;
    }
    virtual void Disconnect() { connected_ = false; }
    virtual bool IsConnected() const { return connected_; }

    void Process(int input) override {
        if (!connected_) return;
        last_result_ = input * 2;
    }

protected:
    std::string host_;
    int port_;
    bool connected_;
};

class CacheComponent : public virtual BaseComponent {
public:
    CacheComponent() : cache_size_(1024), hit_count_(0) {}
    virtual ~CacheComponent() {}

    virtual void SetCacheSize(int size) { cache_size_ = size; }
    virtual int GetHitCount() const { return hit_count_; }
    virtual bool Lookup(int key) {
        hit_count_++;
        return key % 2 == 0;  // 假的 cache hit
    }

    void Process(int input) override {
        if (Lookup(input)) {
            last_result_ = input;
        } else {
            last_result_ = -1;
        }
    }

protected:
    int cache_size_;
    int hit_count_;
};

// 钻石继承
class SuperComponent : public NetworkComponent, public CacheComponent {
public:
    SuperComponent() {}
    ~SuperComponent() override {}

    void Process(int input) override {
        // 调用两条路径
        NetworkComponent::Process(input);
        int net_result = last_result_;
        CacheComponent::Process(input);
        int cache_result = last_result_;
        last_result_ = net_result + cache_result;
    }

    std::string Serialize() const override {
        return name_ + ":" + std::to_string(id_);
    }
    bool Deserialize(const std::string& data) override {
        name_ = data;
        return true;
    }
    void LogState() const override {}
};

// ============================================================
// 宏丛林 — 平台抽象混在业务逻辑中
// ============================================================
#define PLATFORM_WINDOWS 1
#define PLATFORM_LINUX   2
#define PLATFORM_MACOS   3

#ifndef CURRENT_PLATFORM
    #ifdef _WIN32
        #define CURRENT_PLATFORM PLATFORM_WINDOWS
    #elif defined(__APPLE__)
        #define CURRENT_PLATFORM PLATFORM_MACOS
    #else
        #define CURRENT_PLATFORM PLATFORM_LINUX
    #endif
#endif

#define LOG_ERROR(msg)   do { g_error_history.push_back(msg); } while(0)
#define LOG_WARNING(msg) ((void)(msg))
#define LOG_INFO(msg)    ((void)(msg))
#define LOG_DEBUG(msg)   ((void)(msg))

#define SAFE_DELETE(ptr) do { if (ptr) { delete ptr; ptr = nullptr; } } while(0)
#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof(arr[0]))

#define CHECK_RETURN(cond, retval) \
    do { if (!(cond)) { LOG_ERROR("CHECK failed: " #cond); return retval; } } while(0)

#define BEGIN_CRITICAL_SECTION()  /* mutex lock placeholder */
#define END_CRITICAL_SECTION()    /* mutex unlock placeholder */

// ============================================================
// God Function — 核心处理逻辑（过长、过复杂）
// ============================================================
int ProcessLegacyRequest(
    BaseComponent* component,
    const std::string& request_type,
    const std::vector<int>& params,
    std::string* output,
    int flags)
{
    LOG_INFO("ProcessLegacyRequest enter");
    CHECK_RETURN(component != nullptr, -1);
    CHECK_RETURN(output != nullptr, -2);
    CHECK_RETURN(!request_type.empty(), -3);

    int result = 0;
    int retry = 0;
    bool success = false;

    BEGIN_CRITICAL_SECTION();

    // 平台分支 #1
#if CURRENT_PLATFORM == PLATFORM_WINDOWS
    LOG_DEBUG("Windows path");
    if (flags & 0x01) {
        result = component->GetId() * 2;
    }
#elif CURRENT_PLATFORM == PLATFORM_LINUX
    LOG_DEBUG("Linux path");
    if (flags & 0x01) {
        result = component->GetId() * 3;
    }
    #ifdef FEATURE_EXTENDED_LOGGING
        LOG_DEBUG("Extended logging enabled");
        #ifdef FEATURE_VERBOSE
            LOG_DEBUG("Verbose mode");
        #endif
    #endif
#else
    result = component->GetId();
#endif

    // Type dispatch — 应该是策略模式
    if (request_type == "init") {
        component->SetId(params.empty() ? 0 : params[0]);
        component->Process(0);
        result = component->GetResult();

        if (result < 0) {
            LOG_ERROR("init failed");
            for (retry = 0; retry < g_retry_count; ++retry) {
                component->Process(retry);
                result = component->GetResult();
                if (result >= 0) {
                    success = true;
                    break;
                }
            }
            if (!success) {
                END_CRITICAL_SECTION();
                return -100;
            }
        }
    } else if (request_type == "compute") {
        if (params.size() < 2) {
            LOG_WARNING("compute needs 2 params");
            END_CRITICAL_SECTION();
            return -4;
        }

        int sum = 0;
        for (size_t i = 0; i < params.size(); ++i) {
            // 虚调用在循环中 — 性能热点
            component->Process(params[i]);
            int r = component->GetResult();

            if (r < 0) {
                LOG_WARNING("negative result");
                #ifdef FEATURE_STRICT_MODE
                    END_CRITICAL_SECTION();
                    return -200;
                #else
                    r = 0;
                #endif
            }

            switch (params[i] % 5) {
                case 0: sum += r; break;
                case 1: sum += r * 2; break;
                case 2: sum -= r; break;
                case 3: sum += r / 2; break;
                case 4: sum += r % 7; break;
            }

            if (sum > 10000) {
                LOG_WARNING("overflow guard");
                sum = 10000;
            } else if (sum < -10000) {
                sum = -10000;
            }
        }
        result = sum;

    } else if (request_type == "serialize") {
        std::string data = component->Serialize();
        *output = data;
        result = static_cast<int>(data.size());

    } else if (request_type == "deserialize") {
        if (output->empty()) {
            LOG_ERROR("empty deserialize input");
            END_CRITICAL_SECTION();
            return -5;
        }
        success = component->Deserialize(*output);
        result = success ? 1 : 0;

    } else if (request_type == "network_op") {
        // 强制向下转型 — 不安全
        NetworkComponent* net = reinterpret_cast<NetworkComponent*>(component);
        if (flags & 0x10) {
            net->Connect("localhost", 9090);
        }
        net->Process(params.empty() ? 0 : params[0]);
        result = net->GetResult();

        if (!net->IsConnected()) {
            LOG_ERROR("network disconnected");
            result = -300;
        }

    } else if (request_type == "cache_op") {
        // 又一次不安全转型
        CacheComponent* cache = reinterpret_cast<CacheComponent*>(component);
        for (size_t i = 0; i < params.size() && i < 100; ++i) {
            if (cache->Lookup(params[i])) {
                result++;
            }
        }

    } else if (request_type == "batch") {
        // 递归调用自身 — 难以测试和理解
        for (size_t i = 0; i < params.size(); ++i) {
            std::vector<int> sub_params(params.begin() + i, params.end());
            std::string sub_output;
            int sub_result = ProcessLegacyRequest(
                component, "compute", sub_params, &sub_output, flags);
            result += sub_result;
            if (sub_result < -50) {
                LOG_ERROR("batch sub-task failed");
                break;
            }
        }

    } else {
        LOG_WARNING("unknown request type");

        // 平台分支 #2
#if CURRENT_PLATFORM == PLATFORM_LINUX
        // Linux 专用 fallback
        component->Process(-1);
        result = component->GetResult();
#endif
        result = -999;
    }

    // 后处理
    g_global_counter++;
    if (result > 0) {
        *output = std::to_string(result);
    }

    // 平台分支 #3
#ifdef FEATURE_AUDIT_TRAIL
    #if CURRENT_PLATFORM == PLATFORM_WINDOWS
        LOG_INFO("audit: windows");
    #elif CURRENT_PLATFORM == PLATFORM_LINUX
        LOG_INFO("audit: linux");
        #ifdef FEATURE_EXTENDED_AUDIT
            LOG_DEBUG("extended audit data");
        #endif
    #endif
#endif

    END_CRITICAL_SECTION();
    LOG_INFO("ProcessLegacyRequest exit");
    return result;
}

// ============================================================
// 又一个 God Function — 资源管理灾难
// ============================================================
int InitializeSubsystem(int mode, const char* config_path) {
    LOG_INFO("InitializeSubsystem");

    // 裸指针分配 — 资源泄漏风险
    BaseComponent* primary = nullptr;
    BaseComponent* secondary = nullptr;
    char* buffer = nullptr;

    if (mode == 1) {
        primary = new NetworkComponent();
        secondary = new CacheComponent();
    } else if (mode == 2) {
        primary = new SuperComponent();
        secondary = new NetworkComponent();
    } else {
        primary = new BaseComponent();
        secondary = new BaseComponent();
    }

    // 裸 malloc — C/C++ 混合
    buffer = static_cast<char*>(std::malloc(4096));
    if (!buffer) {
        // 泄漏！primary 和 secondary 不会被释放
        LOG_ERROR("malloc failed");
        return -1;
    }

    // 模拟配置读取
    if (config_path) {
        std::strncpy(buffer, config_path, 4095);
        buffer[4095] = '\0';
    }

    // 使用 const_cast 去 const — 危险操作
    const std::string* const_name = &g_log_prefix;
    std::string* mutable_name = const_cast<std::string*>(const_name);
    *mutable_name = "SUBSYS_" + std::string(buffer);

    primary->SetId(mode * 100);
    secondary->SetId(mode * 200);

    primary->Process(42);
    secondary->Process(24);

    int result = primary->GetResult() + secondary->GetResult();

    // 条件释放 — 有路径不释放
#ifdef FEATURE_CLEANUP
    SAFE_DELETE(primary);
    SAFE_DELETE(secondary);
    std::free(buffer);
#else
    // 只在这个宏分支才清理部分
    if (mode != 2) {
        delete primary;
        delete secondary;
    }
    // buffer 永远泄漏！
#endif

    return result;
}

// ============================================================
// 小型辅助函数（对比：这些是"正常"代码）
// ============================================================
int CalculateChecksum(const std::vector<int>& data) {
    int sum = 0;
    for (size_t i = 0; i < data.size(); ++i) {
        sum ^= data[i];
        sum = (sum << 3) | (sum >> 29);
    }
    return sum;
}

bool ValidateInput(const std::string& input, int min_len, int max_len) {
    if (static_cast<int>(input.size()) < min_len) return false;
    if (static_cast<int>(input.size()) > max_len) return false;
    for (char c : input) {
        if (c < 32 || c > 126) return false;
    }
    return true;
}

std::string FormatOutput(int code, const std::string& message) {
    return "[" + std::to_string(code) + "] " + message;
}

// ============================================================
// 模板函数（正常模式，用于对比检测）
// ============================================================
template <typename T>
T ClampValue(T value, T min_val, T max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

template <typename Container>
int CountNegatives(const Container& c) {
    int count = 0;
    for (const auto& item : c) {
        if (item < 0) ++count;
    }
    return count;
}
