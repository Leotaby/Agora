#include "renderer.h"
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
#include <sstream>
#include <iomanip>

// ═══════════════════════════════════════════════════════════════════
// Shaders
// ═══════════════════════════════════════════════════════════════════

static const char* OBJ_VERT = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
uniform mat4 uMVP;
uniform mat4 uModel;
out vec3 vNorm;
out vec3 vWorldPos;
void main() {
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorldPos = wp.xyz;
    vNorm = mat3(transpose(inverse(uModel))) * aNorm;
    gl_Position = uMVP * vec4(aPos, 1.0);
}
)";

static const char* OBJ_FRAG = R"(
#version 330 core
in vec3 vNorm;
in vec3 vWorldPos;
uniform vec3 uColor;
uniform float uGlow;
uniform float uTime;
uniform vec3 uEye;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNorm);
    vec3 L = normalize(vec3(1.0, 2.0, 1.5));
    vec3 V = normalize(uEye - vWorldPos);
    vec3 H = normalize(L + V);

    float diff = max(dot(N, L), 0.0);
    float spec = pow(max(dot(N, H), 0.0), 32.0);

    vec3 ambient = 0.15 * uColor;
    vec3 diffuse = 0.7 * diff * uColor;
    vec3 specular = 0.3 * spec * vec3(1.0);

    vec3 color = ambient + diffuse + specular;

    // Glow pulse for affected banks
    if (uGlow > 0.0) {
        float pulse = 0.5 + 0.5 * sin(uTime * 6.0);
        color += uColor * uGlow * pulse * 0.6;
    }

    FragColor = vec4(color, 1.0);
}
)";

static const char* TEXT_VERT = R"(
#version 330 core
layout(location=0) in vec2 aPos;
layout(location=1) in vec2 aUV;
uniform mat4 uProj;
out vec2 vUV;
void main() {
    gl_Position = uProj * vec4(aPos, 0.0, 1.0);
    vUV = aUV;
}
)";

static const char* TEXT_FRAG = R"(
#version 330 core
in vec2 vUV;
uniform sampler2D uTex;
uniform vec3 uColor;
out vec4 FragColor;
void main() {
    float a = texture(uTex, vUV).r;
    if (a < 0.5) discard;
    FragColor = vec4(uColor, a);
}
)";

// ═══════════════════════════════════════════════════════════════════
// 5x7 bitmap font for ASCII 32-126
// Each char: 7 bytes, bits 4..0 = pixels (bit 4 = left)
// ═══════════════════════════════════════════════════════════════════

static const unsigned char FONT_5x7[95][7] = {
    {0x00,0x00,0x00,0x00,0x00,0x00,0x00}, //   32
    {0x04,0x04,0x04,0x04,0x04,0x00,0x04}, // ! 33
    {0x0A,0x0A,0x0A,0x00,0x00,0x00,0x00}, // " 34
    {0x0A,0x0A,0x1F,0x0A,0x1F,0x0A,0x0A}, // # 35
    {0x04,0x0F,0x14,0x0E,0x05,0x1E,0x04}, // $ 36
    {0x18,0x19,0x02,0x04,0x08,0x13,0x03}, // % 37
    {0x0C,0x12,0x14,0x08,0x15,0x12,0x0D}, // & 38
    {0x04,0x04,0x08,0x00,0x00,0x00,0x00}, // ' 39
    {0x02,0x04,0x08,0x08,0x08,0x04,0x02}, // ( 40
    {0x08,0x04,0x02,0x02,0x02,0x04,0x08}, // ) 41
    {0x00,0x04,0x15,0x0E,0x15,0x04,0x00}, // * 42
    {0x00,0x04,0x04,0x1F,0x04,0x04,0x00}, // + 43
    {0x00,0x00,0x00,0x00,0x0C,0x04,0x08}, // , 44
    {0x00,0x00,0x00,0x1F,0x00,0x00,0x00}, // - 45
    {0x00,0x00,0x00,0x00,0x00,0x0C,0x0C}, // . 46
    {0x00,0x01,0x02,0x04,0x08,0x10,0x00}, // / 47
    {0x0E,0x11,0x13,0x15,0x19,0x11,0x0E}, // 0 48
    {0x04,0x0C,0x04,0x04,0x04,0x04,0x0E}, // 1 49
    {0x0E,0x11,0x01,0x02,0x04,0x08,0x1F}, // 2 50
    {0x1F,0x02,0x04,0x02,0x01,0x11,0x0E}, // 3 51
    {0x02,0x06,0x0A,0x12,0x1F,0x02,0x02}, // 4 52
    {0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E}, // 5 53
    {0x06,0x08,0x10,0x1E,0x11,0x11,0x0E}, // 6 54
    {0x1F,0x01,0x02,0x04,0x04,0x04,0x04}, // 7 55
    {0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E}, // 8 56
    {0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C}, // 9 57
    {0x00,0x0C,0x0C,0x00,0x0C,0x0C,0x00}, // : 58
    {0x00,0x0C,0x0C,0x00,0x0C,0x04,0x08}, // ; 59
    {0x02,0x04,0x08,0x10,0x08,0x04,0x02}, // < 60
    {0x00,0x00,0x1F,0x00,0x1F,0x00,0x00}, // = 61
    {0x08,0x04,0x02,0x01,0x02,0x04,0x08}, // > 62
    {0x0E,0x11,0x01,0x02,0x04,0x00,0x04}, // ? 63
    {0x0E,0x11,0x17,0x15,0x17,0x10,0x0E}, // @ 64
    {0x0E,0x11,0x11,0x1F,0x11,0x11,0x11}, // A 65
    {0x1E,0x11,0x11,0x1E,0x11,0x11,0x1E}, // B 66
    {0x0E,0x11,0x10,0x10,0x10,0x11,0x0E}, // C 67
    {0x1C,0x12,0x11,0x11,0x11,0x12,0x1C}, // D 68
    {0x1F,0x10,0x10,0x1E,0x10,0x10,0x1F}, // E 69
    {0x1F,0x10,0x10,0x1E,0x10,0x10,0x10}, // F 70
    {0x0E,0x11,0x10,0x17,0x11,0x11,0x0F}, // G 71
    {0x11,0x11,0x11,0x1F,0x11,0x11,0x11}, // H 72
    {0x0E,0x04,0x04,0x04,0x04,0x04,0x0E}, // I 73
    {0x07,0x02,0x02,0x02,0x02,0x12,0x0C}, // J 74
    {0x11,0x12,0x14,0x18,0x14,0x12,0x11}, // K 75
    {0x10,0x10,0x10,0x10,0x10,0x10,0x1F}, // L 76
    {0x11,0x1B,0x15,0x15,0x11,0x11,0x11}, // M 77
    {0x11,0x11,0x19,0x15,0x13,0x11,0x11}, // N 78
    {0x0E,0x11,0x11,0x11,0x11,0x11,0x0E}, // O 79
    {0x1E,0x11,0x11,0x1E,0x10,0x10,0x10}, // P 80
    {0x0E,0x11,0x11,0x11,0x15,0x12,0x0D}, // Q 81
    {0x1E,0x11,0x11,0x1E,0x14,0x12,0x11}, // R 82
    {0x0F,0x10,0x10,0x0E,0x01,0x01,0x1E}, // S 83
    {0x1F,0x04,0x04,0x04,0x04,0x04,0x04}, // T 84
    {0x11,0x11,0x11,0x11,0x11,0x11,0x0E}, // U 85
    {0x11,0x11,0x11,0x11,0x11,0x0A,0x04}, // V 86
    {0x11,0x11,0x11,0x15,0x15,0x1B,0x11}, // W 87
    {0x11,0x11,0x0A,0x04,0x0A,0x11,0x11}, // X 88
    {0x11,0x11,0x0A,0x04,0x04,0x04,0x04}, // Y 89
    {0x1F,0x01,0x02,0x04,0x08,0x10,0x1F}, // Z 90
    {0x0E,0x08,0x08,0x08,0x08,0x08,0x0E}, // [ 91
    {0x00,0x10,0x08,0x04,0x02,0x01,0x00}, // \ 92
    {0x0E,0x02,0x02,0x02,0x02,0x02,0x0E}, // ] 93
    {0x04,0x0A,0x11,0x00,0x00,0x00,0x00}, // ^ 94
    {0x00,0x00,0x00,0x00,0x00,0x00,0x1F}, // _ 95
    {0x08,0x04,0x02,0x00,0x00,0x00,0x00}, // ` 96
    {0x00,0x00,0x0E,0x01,0x0F,0x11,0x0F}, // a 97
    {0x10,0x10,0x16,0x19,0x11,0x11,0x1E}, // b 98
    {0x00,0x00,0x0E,0x10,0x10,0x11,0x0E}, // c 99
    {0x01,0x01,0x0D,0x13,0x11,0x11,0x0F}, // d 100
    {0x00,0x00,0x0E,0x11,0x1F,0x10,0x0E}, // e 101
    {0x06,0x09,0x08,0x1C,0x08,0x08,0x08}, // f 102
    {0x00,0x00,0x0F,0x11,0x0F,0x01,0x0E}, // g 103
    {0x10,0x10,0x16,0x19,0x11,0x11,0x11}, // h 104
    {0x04,0x00,0x0C,0x04,0x04,0x04,0x0E}, // i 105
    {0x02,0x00,0x06,0x02,0x02,0x12,0x0C}, // j 106
    {0x10,0x10,0x12,0x14,0x18,0x14,0x12}, // k 107
    {0x0C,0x04,0x04,0x04,0x04,0x04,0x0E}, // l 108
    {0x00,0x00,0x1A,0x15,0x15,0x11,0x11}, // m 109
    {0x00,0x00,0x16,0x19,0x11,0x11,0x11}, // n 110
    {0x00,0x00,0x0E,0x11,0x11,0x11,0x0E}, // o 111
    {0x00,0x00,0x1E,0x11,0x1E,0x10,0x10}, // p 112
    {0x00,0x00,0x0D,0x13,0x0F,0x01,0x01}, // q 113
    {0x00,0x00,0x16,0x19,0x10,0x10,0x10}, // r 114
    {0x00,0x00,0x0E,0x10,0x0E,0x01,0x1E}, // s 115
    {0x08,0x08,0x1C,0x08,0x08,0x09,0x06}, // t 116
    {0x00,0x00,0x11,0x11,0x11,0x13,0x0D}, // u 117
    {0x00,0x00,0x11,0x11,0x11,0x0A,0x04}, // v 118
    {0x00,0x00,0x11,0x11,0x15,0x15,0x0A}, // w 119
    {0x00,0x00,0x11,0x0A,0x04,0x0A,0x11}, // x 120
    {0x00,0x00,0x11,0x11,0x0F,0x01,0x0E}, // y 121
    {0x00,0x00,0x1F,0x02,0x04,0x08,0x1F}, // z 122
    {0x02,0x04,0x04,0x08,0x04,0x04,0x02}, // { 123
    {0x04,0x04,0x04,0x04,0x04,0x04,0x04}, // | 124
    {0x08,0x04,0x04,0x02,0x04,0x04,0x08}, // } 125
    {0x00,0x00,0x08,0x15,0x02,0x00,0x00}, // ~ 126
};

static const int FONT_W = 5;
static const int FONT_H = 7;
static const int ATLAS_COLS = 16;
static const int ATLAS_ROWS = 6;
static const int CELL_W = 6;  // 5 + 1 spacing
static const int CELL_H = 8;  // 7 + 1 spacing

// ═══════════════════════════════════════════════════════════════════
// Shader compilation
// ═══════════════════════════════════════════════════════════════════

GLuint Renderer::compile_shader(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetShaderInfoLog(s, 512, nullptr, log);
        fprintf(stderr, "Shader error: %s\n", log);
    }
    return s;
}

GLuint Renderer::link_program(GLuint vert, GLuint frag) {
    GLuint p = glCreateProgram();
    glAttachShader(p, vert);
    glAttachShader(p, frag);
    glLinkProgram(p);
    GLint ok;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(p, 512, nullptr, log);
        fprintf(stderr, "Link error: %s\n", log);
    }
    glDeleteShader(vert);
    glDeleteShader(frag);
    return p;
}

// ═══════════════════════════════════════════════════════════════════
// Geometry generation
// ═══════════════════════════════════════════════════════════════════

void Renderer::build_sphere(int stacks, int sectors) {
    struct V { float x, y, z, nx, ny, nz; };
    std::vector<V> verts;
    std::vector<unsigned int> indices;

    for (int i = 0; i <= stacks; i++) {
        float phi = M_PI * (float)i / (float)stacks;
        for (int j = 0; j <= sectors; j++) {
            float theta = 2.0f * M_PI * (float)j / (float)sectors;
            float x = sinf(phi) * cosf(theta);
            float y = cosf(phi);
            float z = sinf(phi) * sinf(theta);
            verts.push_back({x, y, z, x, y, z});
        }
    }

    for (int i = 0; i < stacks; i++) {
        for (int j = 0; j < sectors; j++) {
            int a = i * (sectors + 1) + j;
            int b = a + sectors + 1;
            indices.push_back(a); indices.push_back(b); indices.push_back(a + 1);
            indices.push_back(a + 1); indices.push_back(b); indices.push_back(b + 1);
        }
    }

    sphere_idx_count = (int)indices.size();

    glGenVertexArrays(1, &sphere_vao);
    glGenBuffers(1, &sphere_vbo);
    glGenBuffers(1, &sphere_ebo);
    glBindVertexArray(sphere_vao);
    glBindBuffer(GL_ARRAY_BUFFER, sphere_vbo);
    glBufferData(GL_ARRAY_BUFFER, verts.size() * sizeof(V), verts.data(), GL_STATIC_DRAW);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, sphere_ebo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.size() * sizeof(unsigned int), indices.data(), GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(V), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(V), (void*)(3 * sizeof(float)));
    glBindVertexArray(0);
}

void Renderer::build_cylinder(int segments) {
    struct V { float x, y, z, nx, ny, nz; };
    std::vector<V> verts;
    std::vector<unsigned int> indices;

    // Unit cylinder along Y from 0 to 1, radius 1
    for (int i = 0; i <= 1; i++) {
        float y = (float)i;
        for (int j = 0; j <= segments; j++) {
            float theta = 2.0f * M_PI * (float)j / (float)segments;
            float x = cosf(theta);
            float z = sinf(theta);
            verts.push_back({x, y, z, x, 0, z});
        }
    }

    for (int j = 0; j < segments; j++) {
        int a = j;
        int b = a + segments + 1;
        indices.push_back(a); indices.push_back(b); indices.push_back(a + 1);
        indices.push_back(a + 1); indices.push_back(b); indices.push_back(b + 1);
    }

    cyl_idx_count = (int)indices.size();

    glGenVertexArrays(1, &cyl_vao);
    glGenBuffers(1, &cyl_vbo);
    glGenBuffers(1, &cyl_ebo);
    glBindVertexArray(cyl_vao);
    glBindBuffer(GL_ARRAY_BUFFER, cyl_vbo);
    glBufferData(GL_ARRAY_BUFFER, verts.size() * sizeof(V), verts.data(), GL_STATIC_DRAW);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, cyl_ebo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.size() * sizeof(unsigned int), indices.data(), GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(V), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(V), (void*)(3 * sizeof(float)));
    glBindVertexArray(0);
}

// ═══════════════════════════════════════════════════════════════════
// Font texture
// ═══════════════════════════════════════════════════════════════════

void Renderer::build_font_texture() {
    int tex_w = ATLAS_COLS * CELL_W;
    int tex_h = ATLAS_ROWS * CELL_H;
    std::vector<unsigned char> pixels(tex_w * tex_h, 0);

    for (int ch = 0; ch < 95; ch++) {
        int col = ch % ATLAS_COLS;
        int row = ch / ATLAS_COLS;
        int ox = col * CELL_W;
        int oy = row * CELL_H;
        for (int y = 0; y < FONT_H; y++) {
            unsigned char bits = FONT_5x7[ch][y];
            for (int x = 0; x < FONT_W; x++) {
                if (bits & (1 << (4 - x)))
                    pixels[(oy + y) * tex_w + (ox + x)] = 255;
            }
        }
    }

    glGenTextures(1, &font_tex);
    glBindTexture(GL_TEXTURE_2D, font_tex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, tex_w, tex_h, 0,
                 GL_RED, GL_UNSIGNED_BYTE, pixels.data());
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

void Renderer::build_quad() {
    glGenVertexArrays(1, &quad_vao);
    glGenBuffers(1, &quad_vbo);
    glBindVertexArray(quad_vao);
    glBindBuffer(GL_ARRAY_BUFFER, quad_vbo);
    // Will update dynamically
    glBufferData(GL_ARRAY_BUFFER, 4096 * 4 * sizeof(float), nullptr, GL_DYNAMIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));
    glBindVertexArray(0);
}

// ═══════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════

void Renderer::init() {
    obj_prog = link_program(
        compile_shader(GL_VERTEX_SHADER, OBJ_VERT),
        compile_shader(GL_FRAGMENT_SHADER, OBJ_FRAG)
    );
    text_prog = link_program(
        compile_shader(GL_VERTEX_SHADER, TEXT_VERT),
        compile_shader(GL_FRAGMENT_SHADER, TEXT_FRAG)
    );

    build_sphere(16, 24);
    build_cylinder(16);
    build_font_texture();
    build_quad();

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
}

// ═══════════════════════════════════════════════════════════════════
// Color mapping
// ═══════════════════════════════════════════════════════════════════

glm::vec3 Renderer::status_color(const std::string& status, const std::string& type) {
    if (type == "central_bank") return glm::vec3(0.2f, 0.4f, 0.9f);
    if (status == "normal")     return glm::vec3(0.0f, 0.784f, 0.588f); // #00C896
    if (status == "stressed")   return glm::vec3(0.941f, 0.659f, 0.196f); // #F0A832
    if (status == "critical")   return glm::vec3(0.910f, 0.365f, 0.188f); // #E85D30
    if (status == "failed" || status == "resolution")
                                return glm::vec3(0.910f, 0.251f, 0.251f); // #E84040
    return glm::vec3(0.6f, 0.6f, 0.6f);
}

// ═══════════════════════════════════════════════════════════════════
// Draw helpers
// ═══════════════════════════════════════════════════════════════════

void Renderer::draw_bank(const BankNode& node, const glm::mat4& vp,
                         float time, bool glowing)
{
    glm::mat4 model = glm::translate(glm::mat4(1.0f), node.position);
    float s = node.radius;
    if (glowing) s *= 1.0f + 0.08f * sinf(time * 6.0f);
    model = glm::scale(model, glm::vec3(s));

    glm::mat4 mvp = vp * model;
    glm::vec3 color = status_color(node.status, node.type);

    glUseProgram(obj_prog);
    glUniformMatrix4fv(glGetUniformLocation(obj_prog, "uMVP"), 1, GL_FALSE, glm::value_ptr(mvp));
    glUniformMatrix4fv(glGetUniformLocation(obj_prog, "uModel"), 1, GL_FALSE, glm::value_ptr(model));
    glUniform3fv(glGetUniformLocation(obj_prog, "uColor"), 1, glm::value_ptr(color));
    glUniform1f(glGetUniformLocation(obj_prog, "uGlow"), glowing ? 1.0f : 0.0f);
    glUniform1f(glGetUniformLocation(obj_prog, "uTime"), time);

    glBindVertexArray(sphere_vao);
    glDrawElements(GL_TRIANGLES, sphere_idx_count, GL_UNSIGNED_INT, 0);
}

void Renderer::draw_edge(const glm::vec3& from, const glm::vec3& to,
                         float thickness, const glm::vec4& color,
                         const glm::mat4& vp)
{
    glm::vec3 dir = to - from;
    float len = glm::length(dir);
    if (len < 0.001f) return;
    glm::vec3 ndir = dir / len;

    // Rotation from Y-axis to direction
    glm::vec3 up(0, 1, 0);
    glm::mat4 rot(1.0f);
    float dot = glm::dot(up, ndir);
    if (fabsf(dot + 1.0f) < 0.001f) {
        // Opposite direction
        rot = glm::rotate(glm::mat4(1.0f), (float)M_PI, glm::vec3(1, 0, 0));
    } else if (fabsf(dot - 1.0f) > 0.001f) {
        glm::vec3 axis = glm::normalize(glm::cross(up, ndir));
        float angle = acosf(glm::clamp(dot, -1.0f, 1.0f));
        rot = glm::rotate(glm::mat4(1.0f), angle, axis);
    }

    glm::mat4 model = glm::translate(glm::mat4(1.0f), from);
    model = model * rot;
    model = glm::scale(model, glm::vec3(thickness, len, thickness));

    glm::mat4 mvp = vp * model;

    glUseProgram(obj_prog);
    glUniformMatrix4fv(glGetUniformLocation(obj_prog, "uMVP"), 1, GL_FALSE, glm::value_ptr(mvp));
    glUniformMatrix4fv(glGetUniformLocation(obj_prog, "uModel"), 1, GL_FALSE, glm::value_ptr(model));
    glUniform3f(glGetUniformLocation(obj_prog, "uColor"), color.r, color.g, color.b);
    glUniform1f(glGetUniformLocation(obj_prog, "uGlow"), 0.0f);

    glBindVertexArray(cyl_vao);
    glDrawElements(GL_TRIANGLES, cyl_idx_count, GL_UNSIGNED_INT, 0);
}

// ═══════════════════════════════════════════════════════════════════
// Text rendering
// ═══════════════════════════════════════════════════════════════════

void Renderer::draw_text(const std::string& text, float x, float y,
                         float scale, const glm::vec3& color,
                         int fb_width, int fb_height)
{
    float tex_w = (float)(ATLAS_COLS * CELL_W);
    float tex_h = (float)(ATLAS_ROWS * CELL_H);
    float cw = CELL_W * scale;
    float ch = CELL_H * scale;

    // Build quad vertices: pos.xy, uv.xy
    std::vector<float> verts;
    float cx = x;
    for (char c : text) {
        int idx = (int)c - 32;
        if (idx < 0 || idx >= 95) { cx += cw; continue; }
        int col = idx % ATLAS_COLS;
        int row = idx / ATLAS_COLS;
        float u0 = (float)(col * CELL_W) / tex_w;
        float v0 = (float)(row * CELL_H) / tex_h;
        float u1 = (float)(col * CELL_W + CELL_W) / tex_w;
        float v1 = (float)(row * CELL_H + CELL_H) / tex_h;

        float x0 = cx, x1 = cx + cw;
        float y0 = y,  y1 = y + ch;

        // Two triangles per quad
        float q[] = {
            x0,y0, u0,v0,  x1,y0, u1,v0,  x1,y1, u1,v1,
            x0,y0, u0,v0,  x1,y1, u1,v1,  x0,y1, u0,v1,
        };
        verts.insert(verts.end(), q, q + 24);
        cx += cw;
    }

    if (verts.empty()) return;

    glm::mat4 proj = glm::ortho(0.0f, (float)fb_width, (float)fb_height, 0.0f);

    glUseProgram(text_prog);
    glUniformMatrix4fv(glGetUniformLocation(text_prog, "uProj"), 1, GL_FALSE, glm::value_ptr(proj));
    glUniform3fv(glGetUniformLocation(text_prog, "uColor"), 1, glm::value_ptr(color));
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, font_tex);
    glUniform1i(glGetUniformLocation(text_prog, "uTex"), 0);

    glBindVertexArray(quad_vao);
    glBindBuffer(GL_ARRAY_BUFFER, quad_vbo);
    glBufferSubData(GL_ARRAY_BUFFER, 0, verts.size() * sizeof(float), verts.data());
    glDrawArrays(GL_TRIANGLES, 0, (int)verts.size() / 4);
    glBindVertexArray(0);
}

// ═══════════════════════════════════════════════════════════════════
// Main scene draw
// ═══════════════════════════════════════════════════════════════════

void Renderer::draw_scene(
    const SimulationData& sim,
    const Camera& cam,
    int current_round,
    float time,
    const std::set<std::string>& affected_banks,
    const std::set<std::pair<std::string,std::string>>& active_edges,
    int fb_width, int fb_height)
{
    glm::mat4 view = cam.view();
    glm::mat4 proj = cam.projection((float)fb_width / (float)fb_height);
    glm::mat4 vp = proj * view;

    // Set eye position for specular
    glUseProgram(obj_prog);
    glm::vec3 eye = cam.eye();
    glUniform3fv(glGetUniformLocation(obj_prog, "uEye"), 1, glm::value_ptr(eye));

    // Find max edge amount for thickness scaling
    float max_amount = 1.0f;
    for (auto& e : sim.edges)
        max_amount = std::max(max_amount, e.amount);

    // Draw edges (default: grey, active: red)
    for (auto& e : sim.edges) {
        auto it_src = sim.node_index.find(e.source);
        auto it_tgt = sim.node_index.find(e.target);
        if (it_src == sim.node_index.end() || it_tgt == sim.node_index.end()) continue;

        glm::vec3 from = sim.nodes[it_src->second].position;
        glm::vec3 to = sim.nodes[it_tgt->second].position;

        // Offset slightly from center of sphere
        glm::vec3 dir = glm::normalize(to - from);
        from += dir * sim.nodes[it_src->second].radius * 0.8f;
        to -= dir * sim.nodes[it_tgt->second].radius * 0.8f;

        float thick = 0.02f + 0.08f * (e.amount / max_amount);

        bool is_active = active_edges.count({e.source, e.target}) > 0 ||
                         active_edges.count({e.target, e.source}) > 0;

        if (is_active) {
            float pulse = 0.7f + 0.3f * sinf(time * 8.0f);
            draw_edge(from, to, thick * 2.0f,
                      glm::vec4(1.0f, 0.15f, 0.05f, pulse), vp);
        } else {
            draw_edge(from, to, thick,
                      glm::vec4(0.35f, 0.38f, 0.45f, 0.5f), vp);
        }
    }

    // Draw bank spheres
    for (auto& node : sim.nodes) {
        bool glowing = affected_banks.count(node.id) > 0;
        draw_bank(node, vp, time, glowing);
    }

    // Draw labels above spheres (3D projected to 2D)
    glDisable(GL_DEPTH_TEST);
    glm::vec4 viewport(0, 0, fb_width, fb_height);
    for (auto& node : sim.nodes) {
        glm::vec3 label_pos = node.position + glm::vec3(0, node.radius + 0.4f, 0);
        glm::vec3 screen = glm::project(label_pos, view, proj, viewport);

        // Behind camera check
        if (screen.z < 0.0f || screen.z > 1.0f) continue;

        // Flip Y (project gives bottom-up, our ortho is top-down)
        float sx = screen.x;
        float sy = (float)fb_height - screen.y;

        // Bank name
        float name_scale = 2.5f;
        float name_w = node.name.size() * CELL_W * name_scale;
        draw_text(node.name, sx - name_w / 2.0f, sy - CELL_H * name_scale - 4,
                  name_scale, glm::vec3(1.0f), fb_width, fb_height);

        // CET1 ratio
        if (node.type != "central_bank") {
            std::ostringstream oss;
            oss << std::fixed << std::setprecision(1) << node.cet1_ratio_pct << "%";
            std::string cet1_str = oss.str();
            float cet1_scale = 1.8f;
            float cet1_w = cet1_str.size() * CELL_W * cet1_scale;
            draw_text(cet1_str, sx - cet1_w / 2.0f, sy + 2,
                      cet1_scale, glm::vec3(0.8f, 0.85f, 0.9f), fb_width, fb_height);
        }
    }
    glEnable(GL_DEPTH_TEST);
}

// ═══════════════════════════════════════════════════════════════════
// HUD
// ═══════════════════════════════════════════════════════════════════

void Renderer::draw_hud(
    int current_round,
    const std::string& label,
    float cumulative_loss,
    int banks_stressed,
    int banks_failed,
    bool auto_play,
    int total_rounds,
    int fb_width, int fb_height)
{
    glDisable(GL_DEPTH_TEST);

    // Draw dark background bar at bottom
    {
        float bar_h = 70.0f;
        float y0 = (float)fb_height - bar_h;
        float verts[] = {
            0, y0,         0, 0,
            (float)fb_width, y0,  1, 0,
            (float)fb_width, (float)fb_height, 1, 1,
            0, y0,         0, 0,
            (float)fb_width, (float)fb_height, 1, 1,
            0, (float)fb_height, 0, 1,
        };
        glm::mat4 proj = glm::ortho(0.0f, (float)fb_width, (float)fb_height, 0.0f);
        glUseProgram(text_prog);
        glUniformMatrix4fv(glGetUniformLocation(text_prog, "uProj"), 1, GL_FALSE, glm::value_ptr(proj));
        // Use a solid color trick: bind font tex, but with a uniform color and alpha
        // Actually we need a separate solid-color draw. Let's just use text on a dark area
        // We'll skip the background quad for simplicity and just draw bright text
    }

    float y_line1 = (float)fb_height - 55.0f;
    float y_line2 = (float)fb_height - 28.0f;
    float scale = 2.2f;

    // Line 1: Round info and losses
    {
        std::ostringstream oss;
        if (current_round < 0)
            oss << "Pre-Shock";
        else
            oss << "Round " << current_round << "/" << (total_rounds - 1)
                << "  " << label;
        oss << "    Loss: EUR " << std::fixed << std::setprecision(1) << cumulative_loss << "bn";
        oss << "    Stressed: " << banks_stressed;
        if (banks_failed > 0) oss << "  Failed: " << banks_failed;

        draw_text(oss.str(), 12, y_line1, scale, glm::vec3(1.0f, 0.95f, 0.85f),
                  fb_width, fb_height);
    }

    // Line 2: Controls
    {
        std::ostringstream oss;
        oss << "[SPACE] Next  [A] Auto-play";
        if (auto_play) oss << " ON";
        oss << "  [R] Reset  [ESC] Quit";
        draw_text(oss.str(), 12, y_line2, 1.8f, glm::vec3(0.5f, 0.55f, 0.6f),
                  fb_width, fb_height);
    }

    glEnable(GL_DEPTH_TEST);
}
