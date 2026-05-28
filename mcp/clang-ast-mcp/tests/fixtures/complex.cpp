// Test fixture: complex C++ patterns to stress all 4 analyzers.
//
// Covers (beyond sample.cpp):
//   - templates (function template, class template)
//   - multi-level inheritance (Grandparent -> Parent -> Child)
//   - multiple inheritance (mix-in with two virtual bases)
//   - nested namespaces (a::b::c)
//   - operator overloading
//   - lambdas inside method bodies
//   - constexpr / inline function
//   - thread_local + static const
//
// Expected detections:
//   - >=10 function definitions (counting templates as 1)
//   - >=6 globals across linkage kinds
//   - >=2 virtual call sites (Compute via Parent*, Render via Drawable*)
//   - macro_jungle: process_complex has nested #ifdef + macros

#include <string>
#include <vector>
#include <memory>

// ------------- Globals (multiple linkages) -------------
extern int g_extern_var;                    // EXPECT: extern
static int g_file_static = 100;             // EXPECT: file_static
namespace {
    int g_anon_one = 1;                     // EXPECT: anon_ns
    static const int g_anon_two = 2;        // EXPECT: anon_ns
}
namespace outer {
    int g_in_named_ns = 10;                 // EXPECT: extern (named ns global)
    namespace inner {
        int g_deep = 20;                    // EXPECT: extern
    }
}
thread_local int g_tls = 0;                 // EXPECT: extern (tls)

// ------------- Multi-level inheritance + virtuals -------------
class Grandparent {
public:
    virtual ~Grandparent() {}
    virtual int Compute(int x) const { return x; }
    virtual int Compute(int x, int y) const { return x + y; }  // overload
    static int s_grand_count;
};
int Grandparent::s_grand_count = 0;          // EXPECT: class_static

class Parent : public Grandparent {
public:
    int Compute(int x) const override { return x * 2; }
};

class Child : public Parent {
public:
    int Compute(int x) const override { return x * 3; }
    int Compute(int x, int y) const override { return x * y; }
};

// ------------- Multiple inheritance / mix-in -------------
class Drawable {
public:
    virtual ~Drawable() {}
    virtual void Render() const {}
};

class Sized {
public:
    virtual ~Sized() {}
    virtual int Width() const { return 0; }
};

class Widget : public Drawable, public Sized {
public:
    void Render() const override {}
    int Width() const override { return 42; }
};

// ------------- Function templates -------------
template <typename T>
T add_one(T value) {
    return value + T(1);
}

template <typename T, typename U>
auto mul(T a, U b) -> decltype(a * b) {
    return a * b;
}

// ------------- Class template -------------
template <typename T>
class Container {
public:
    Container() : data_() {}
    void Push(const T& v) { data_.push_back(v); }
    std::size_t Size() const { return data_.size(); }
private:
    std::vector<T> data_;
};

// ------------- Operator overloading -------------
struct Vec2 {
    double x, y;
    Vec2 operator+(const Vec2& o) const { return {x + o.x, y + o.y}; }
    bool operator==(const Vec2& o) const { return x == o.x && y == o.y; }
};

// ------------- constexpr + inline -------------
constexpr int square(int n) { return n * n; }
inline int cube(int n) { return n * n * n; }

// ------------- Macro / #ifdef jungle (target for macro_jungle) -------------
#define FEATURE_A 1
#define FEATURE_B 1
#define LOG_DEBUG(msg) ((void)(msg))
#define LOG_TRACE(msg) ((void)(msg))

int process_complex(Grandparent* gp, Drawable* d, int input) {
    LOG_DEBUG("entering process_complex");
    int result = 0;

#ifdef FEATURE_A
    LOG_TRACE("feature A enabled");
    result = gp->Compute(input);                  // EXPECT: virtual call (Compute(int))
    #ifdef FEATURE_B
        result += gp->Compute(input, 2);          // EXPECT: virtual call (Compute(int,int))
    #else
        result += input;
    #endif
#else
    result = input;
#endif

#if defined(__linux__)
    d->Render();                                  // EXPECT: virtual call
    result += g_file_static;
#elif defined(_WIN32)
    result += 1;
#elif defined(__APPLE__)
    result += 2;
#else
    result += 3;
#endif

    // Lambda body — should NOT count as separate function definition
    auto adder = [](int a, int b) { return a + b; };
    result = adder(result, 0);

    return result;
}

// ------------- Long simple function for min_lines filter test -------------
int LongComplexFunction(int a) {
    int x = a;
    for (int i = 0; i < 10; ++i) {
        if (i % 2 == 0) {
            x += i;
        } else {
            x -= i;
        }
    }
    if (x > 1000) {
        x = 1000;
    } else if (x < -1000) {
        x = -1000;
    }
    return x;
}
