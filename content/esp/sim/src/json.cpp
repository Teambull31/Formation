#include "json.h"

#include <cmath>
#include <cstdlib>

namespace sim {

const Json *Json::get(const std::string &key) const {
    for (const auto &m : obj)
        if (m.first == key) return &m.second;
    return nullptr;
}

bool Json::as_int(long long lo, long long hi, long long &out) const {
    if (type != Number || num != std::floor(num) || num < static_cast<double>(lo) || num > static_cast<double>(hi))
        return false;
    out = static_cast<long long>(num);
    return true;
}

namespace {

constexpr int kMaxDepth = 64;  // keeps hostile nesting from overflowing the stack

struct Parser {
    const std::string &s;
    size_t i = 0;
    std::string err;

    bool fail(const char *what) {
        if (err.empty()) err = std::string(what) + " à l'octet " + std::to_string(i);
        return false;
    }
    void ws() {
        while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i;
    }
    bool lit(const char *word) {
        size_t n = std::char_traits<char>::length(word);
        if (s.compare(i, n, word) != 0) return fail("valeur JSON invalide");
        i += n;
        return true;
    }
    bool hex4(unsigned &cp) {
        if (i + 4 > s.size()) return fail("séquence \\u tronquée");
        cp = 0;
        for (int k = 0; k < 4; ++k) {
            char c = s[i++];
            cp <<= 4;
            if (c >= '0' && c <= '9') cp |= c - '0';
            else if (c >= 'a' && c <= 'f') cp |= c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') cp |= c - 'A' + 10;
            else return fail("chiffre hexadécimal invalide");
        }
        return true;
    }
    static void utf8(std::string &out, unsigned cp) {
        if (cp < 0x80) out += static_cast<char>(cp);
        else if (cp < 0x800) { out += static_cast<char>(0xC0 | cp >> 6); out += static_cast<char>(0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) {
            out += static_cast<char>(0xE0 | cp >> 12);
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | cp >> 18);
            out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }
    bool string(std::string &out) {
        ++i;  // opening quote
        for (;;) {
            if (i >= s.size()) return fail("chaîne non terminée");
            unsigned char c = static_cast<unsigned char>(s[i++]);
            if (c == '"') return true;
            if (c < 0x20) return fail("caractère de contrôle dans une chaîne");
            if (c != '\\') { out += static_cast<char>(c); continue; }
            if (i >= s.size()) return fail("chaîne non terminée");
            char e = s[i++];
            switch (e) {
                case '"': case '\\': case '/': out += e; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'u': {
                    unsigned cp;
                    if (!hex4(cp)) return false;
                    if (cp >= 0xD800 && cp < 0xDC00) {  // high surrogate: needs a low one
                        unsigned lo;
                        if (s.compare(i, 2, "\\u") != 0) return fail("surrogate isolé");
                        i += 2;
                        if (!hex4(lo)) return false;
                        if (lo < 0xDC00 || lo > 0xDFFF) return fail("surrogate invalide");
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                    } else if (cp >= 0xDC00 && cp <= 0xDFFF) {
                        return fail("surrogate isolé");
                    }
                    utf8(out, cp);
                    break;
                }
                default: return fail("échappement invalide");
            }
        }
    }
    bool number(double &out) {
        size_t start = i;
        auto digits = [&] { size_t n = 0; while (i < s.size() && s[i] >= '0' && s[i] <= '9') { ++i; ++n; } return n; };
        if (i < s.size() && s[i] == '-') ++i;
        if (i < s.size() && s[i] == '0') ++i;
        else if (!digits()) return fail("nombre invalide");
        if (i < s.size() && s[i] == '.') { ++i; if (!digits()) return fail("nombre invalide"); }
        if (i < s.size() && (s[i] == 'e' || s[i] == 'E')) {
            ++i;
            if (i < s.size() && (s[i] == '+' || s[i] == '-')) ++i;
            if (!digits()) return fail("nombre invalide");
        }
        out = std::strtod(s.substr(start, i - start).c_str(), nullptr);
        return true;
    }
    bool value(Json &v, int depth) {
        if (depth > kMaxDepth) return fail("imbrication trop profonde");
        ws();
        if (i >= s.size()) return fail("valeur attendue");
        char c = s[i];
        if (c == '{') {
            v.type = Json::Object;
            ++i;
            ws();
            if (i < s.size() && s[i] == '}') { ++i; return true; }
            for (;;) {
                ws();
                if (i >= s.size() || s[i] != '"') return fail("clé attendue");
                std::string key;
                if (!string(key)) return false;
                ws();
                if (i >= s.size() || s[i] != ':') return fail("':' attendu");
                ++i;
                Json child;
                if (!value(child, depth + 1)) return false;
                v.obj.emplace_back(std::move(key), std::move(child));
                ws();
                if (i < s.size() && s[i] == ',') { ++i; continue; }
                if (i < s.size() && s[i] == '}') { ++i; return true; }
                return fail("',' ou '}' attendu");
            }
        }
        if (c == '[') {
            v.type = Json::Array;
            ++i;
            ws();
            if (i < s.size() && s[i] == ']') { ++i; return true; }
            for (;;) {
                Json child;
                if (!value(child, depth + 1)) return false;
                v.arr.push_back(std::move(child));
                ws();
                if (i < s.size() && s[i] == ',') { ++i; continue; }
                if (i < s.size() && s[i] == ']') { ++i; return true; }
                return fail("',' ou ']' attendu");
            }
        }
        if (c == '"') { v.type = Json::String; return string(v.str); }
        if (c == 't') { v.type = Json::Bool; v.b = true; return lit("true"); }
        if (c == 'f') { v.type = Json::Bool; v.b = false; return lit("false"); }
        if (c == 'n') { v.type = Json::Null; return lit("null"); }
        v.type = Json::Number;
        return number(v.num);
    }
};

}  // namespace

bool only_keys(const Json &object, std::initializer_list<const char *> allowed, const char *where, std::string &err) {
    for (const auto &member : object.obj) {
        bool known = false;
        for (const char *k : allowed) known = known || member.first == k;
        if (!known) {
            err = std::string(where) + " : clé inconnue \"" + member.first + "\"";
            return false;
        }
    }
    return true;
}

bool json_parse(const std::string &text, Json &out, std::string &err) {
    Parser p{text};
    out = Json();
    if (!p.value(out, 0)) { err = p.err; return false; }
    p.ws();
    if (p.i != text.size()) { p.fail("texte après la valeur JSON"); err = p.err; return false; }
    return true;
}

}  // namespace sim
