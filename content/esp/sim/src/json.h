// Small general JSON reader for scenario files (objects, arrays, numbers, strings, bools, null).
#pragma once

#include <initializer_list>
#include <string>
#include <utility>
#include <vector>

namespace sim {

struct Json {
    enum Type { Null, Bool, Number, String, Array, Object } type = Null;
    bool b = false;
    double num = 0;
    std::string str;
    std::vector<Json> arr;
    std::vector<std::pair<std::string, Json>> obj;

    // First member named `key` of an object, or nullptr.
    const Json *get(const std::string &key) const;
    // True when this is a number with an integral value in [lo, hi]; stores it in out.
    bool as_int(long long lo, long long hi, long long &out) const;
};

// False, with err naming `where` and the key, when the object has a member outside `allowed` (a typo in a scenario).
bool only_keys(const Json &object, std::initializer_list<const char *> allowed, const char *where, std::string &err);

// Parses the whole text. On failure returns false and err says what and where (byte offset).
bool json_parse(const std::string &text, Json &out, std::string &err);

}  // namespace sim
