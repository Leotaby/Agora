#pragma once
#include "network.h"
#include "camera.h"
#include <set>
#include <string>

#ifdef __APPLE__
#include <OpenGL/gl3.h>
#else
#include <GL/gl.h>
#endif

class Renderer {
public:
    void init();
    void draw_scene(
        const SimulationData& sim,
        const Camera& cam,
        int current_round,
        float time,
        const std::set<std::string>& affected_banks,
        const std::set<std::pair<std::string,std::string>>& active_edges,
        bool ecb_intervening,
        float ecb_ela_total,
        const std::vector<std::string>& ecb_supported_bank_ids,
        int fb_width, int fb_height
    );
    void draw_hud(
        int current_round,
        const std::string& label,
        float cumulative_loss,
        int banks_stressed,
        int banks_failed,
        bool auto_play,
        int total_rounds,
        bool ecb_intervening,
        float ecb_ela_total,
        int fb_width, int fb_height
    );

private:
    GLuint obj_prog = 0;
    GLuint text_prog = 0;
    GLuint sphere_vao = 0, sphere_vbo = 0, sphere_ebo = 0;
    int sphere_idx_count = 0;
    GLuint cyl_vao = 0, cyl_vbo = 0, cyl_ebo = 0;
    int cyl_idx_count = 0;
    GLuint font_tex = 0;
    GLuint quad_vao = 0, quad_vbo = 0;

    void build_sphere(int stacks, int sectors);
    void build_cylinder(int segments);
    void build_font_texture();
    void build_quad();

    GLuint compile_shader(GLenum type, const char* src);
    GLuint link_program(GLuint vert, GLuint frag);

    void draw_bank(const BankNode& node, const glm::mat4& vp,
                   float time, bool glowing);
    void draw_edge(const glm::vec3& from, const glm::vec3& to,
                   float thickness, const glm::vec4& color,
                   const glm::mat4& vp);
    void draw_text(const std::string& text, float x, float y,
                   float scale, const glm::vec3& color,
                   int fb_width, int fb_height);

    glm::vec3 status_color(const std::string& status, const std::string& type);
};
