#include <unistd.h>

#include <cstdio>

#include "sim.h"

namespace sim {

int trace_fd = STDOUT_FILENO;

namespace {

void append_json_string(std::string &out, const std::string &s) {
    out += '"';
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') {
            out += '\\';
            out += static_cast<char>(c);
        } else if (c < 0x20) {
            char buf[8];
            std::snprintf(buf, sizeof buf, "\\u%04x", c);
            out += buf;
        } else {
            out += static_cast<char>(c);
        }
    }
    out += '"';
}

}  // namespace

Event::Event(int64_t t_ms, const char *ev) {
    line_ = "{\"t_ms\": " + std::to_string(t_ms) + ", \"ev\": ";
    append_json_string(line_, ev);
}

Event &Event::str(const char *key, const std::string &value) {
    line_ += ", ";
    append_json_string(line_, key);
    line_ += ": ";
    append_json_string(line_, value);
    return *this;
}

Event &Event::num(const char *key, int64_t value) {
    line_ += ", ";
    append_json_string(line_, key);
    line_ += ": " + std::to_string(value);
    return *this;
}

Event &Event::flag(const char *key, bool value) {
    line_ += ", ";
    append_json_string(line_, key);
    line_ += value ? ": true" : ": false";
    return *this;
}

// Unbuffered write: nothing is lost when the process ends with _exit or a signal.
Event::~Event() {
    line_ += "}\n";
    const char *p = line_.data();
    size_t left = line_.size();
    while (left > 0) {
        ssize_t n = ::write(trace_fd, p, left);
        if (n <= 0) break;
        p += n;
        left -= static_cast<size_t>(n);
    }
}

}  // namespace sim
