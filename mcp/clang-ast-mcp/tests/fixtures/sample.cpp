// Test fixture: a small but representative C++ file containing
// every code pattern the 4 analyzers should detect.
//
// Expected detections:
//   - 5 functions (incl. virtual + override + ctor + dtor)
//   - 4 globals (extern, file-static, anon-ns, class-static)
//   - 1 virtual call site (in process())
//   - 2 functions with #ifdef branches

#include <string>
#include <vector>

// ------------- Globals -------------
extern int g_extern_counter;             // EXPECT: extern
static int g_file_static = 42;           // EXPECT: file_static
namespace {
    int g_anon_global = 0;               // EXPECT: anon_ns
}

// ------------- Class with statics + virtuals -------------
class Base {
public:
    Base() {}
    virtual ~Base() {}
    virtual int Compute(int x) const { return x * 2; }
    static int s_instance_count;         // EXPECT: class_static (decl only)
};

int Base::s_instance_count = 0;          // EXPECT: class_static (definition)

class Derived : public Base {
public:
    int Compute(int x) const override { return x + 100; }
};

// ------------- Function with #ifdef jungle + macros -------------
#define FEATURE_FOO 1
#define LOG_INFO(msg) ((void)(msg))

int process(Base* obj, int input) {
    LOG_INFO("entering process");
    int result = 0;
#ifdef FEATURE_FOO
    if (input > 0) {
        result = obj->Compute(input);    // EXPECT: virtual call
    } else {
        result = -1;
    }
#else
    result = obj->Compute(input * 2);
#endif

#if defined(__linux__)
    result += g_file_static;
#elif defined(_WIN32)
    result += 1;
#endif

    return result;
}

// ------------- A long simple function (for min_lines filter test) -------------
int LongFunction(int a) {
    int x = a;
    x += 1; x += 2; x += 3; x += 4; x += 5;
    x += 6; x += 7; x += 8; x += 9; x += 10;
    x += 11; x += 12; x += 13; x += 14; x += 15;
    if (x > 100) {
        x = 100;
    }
    return x;
}
