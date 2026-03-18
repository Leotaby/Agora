#include "network.h"
#include "renderer.h"
#include "camera.h"

#include <GLFW/glfw3.h>
#include <iostream>
#include <set>
#include <string>
#include <cmath>

// ── globals ──────────────────────────────────────────────────────

static Camera g_cam;
static SimulationData g_sim;
static Renderer g_renderer;

static int g_current_round = -1;     // -1 = pre-shock
static bool g_auto_play = false;
static float g_auto_timer = 0.0f;
static float g_auto_interval = 1.0f; // seconds per round
static float g_time = 0.0f;

static std::set<std::string> g_affected;
static std::set<std::pair<std::string,std::string>> g_active_edges;

static int g_fb_width = 1280;
static int g_fb_height = 800;

// ── round management ─────────────────────────────────────────────

static void apply_pre_shock() {
    // Reset all nodes to initial state from the simulation data
    // (positions and radii are already computed by layout)
    g_affected.clear();
    g_active_edges.clear();
    g_current_round = -1;
}

static void advance_round() {
    if (g_current_round >= (int)g_sim.rounds.size() - 1) {
        g_auto_play = false;
        return;
    }
    g_current_round++;
    auto& round = g_sim.rounds[g_current_round];

    // Update bank states
    for (auto& [id, state] : round.bank_states) {
        auto it = g_sim.node_index.find(id);
        if (it != g_sim.node_index.end()) {
            auto& node = g_sim.nodes[it->second];
            node.status = state.status;
            node.cet1_ratio_pct = state.cet1_ratio_pct;
            node.lcr_pct = state.lcr_pct;
            node.total_assets = state.total_assets;
            node.credit_spread_bps = state.credit_spread_bps;
        }
    }

    // Update visual state
    g_affected.clear();
    for (auto& b : round.affected_banks)
        g_affected.insert(b);

    g_active_edges.clear();
    for (auto& e : round.active_edges)
        g_active_edges.insert({e.source, e.target});
}

static void reset_simulation() {
    // Reload pre-shock states
    g_sim = fetch_simulation("http://localhost:5001/api/banking/simulate");
    apply_pre_shock();
    g_auto_play = false;
}

// ── GLFW callbacks ───────────────────────────────────────────────

static void key_callback(GLFWwindow* window, int key, int /*scancode*/,
                         int action, int /*mods*/)
{
    if (action != GLFW_PRESS) return;

    switch (key) {
        case GLFW_KEY_SPACE:
            advance_round();
            break;
        case GLFW_KEY_A:
            g_auto_play = !g_auto_play;
            g_auto_timer = 0.0f;
            break;
        case GLFW_KEY_R:
            reset_simulation();
            break;
        case GLFW_KEY_ESCAPE:
            glfwSetWindowShouldClose(window, GLFW_TRUE);
            break;
    }
}

static void mouse_button_callback(GLFWwindow* window, int button, int action, int /*mods*/) {
    if (button == GLFW_MOUSE_BUTTON_LEFT) {
        g_cam.dragging = (action == GLFW_PRESS);
        if (g_cam.dragging)
            glfwGetCursorPos(window, &g_cam.last_x, &g_cam.last_y);
    }
}

static void cursor_pos_callback(GLFWwindow* /*window*/, double xpos, double ypos) {
    if (g_cam.dragging) {
        g_cam.drag(xpos - g_cam.last_x, ypos - g_cam.last_y);
        g_cam.last_x = xpos;
        g_cam.last_y = ypos;
    }
}

static void scroll_callback(GLFWwindow* /*window*/, double /*xoffset*/, double yoffset) {
    g_cam.scroll(yoffset);
}

static void framebuffer_size_callback(GLFWwindow* /*window*/, int width, int height) {
    g_fb_width = width;
    g_fb_height = height;
    glViewport(0, 0, width, height);
}

// ── main ─────────────────────────────────────────────────────────

int main() {
    // Init GLFW
    if (!glfwInit()) {
        std::cerr << "Failed to init GLFW" << std::endl;
        return 1;
    }

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
#ifdef __APPLE__
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
#endif

    GLFWwindow* window = glfwCreateWindow(1280, 800, "AGORA - Banking Contagion Visualizer", nullptr, nullptr);
    if (!window) {
        std::cerr << "Failed to create window" << std::endl;
        glfwTerminate();
        return 1;
    }

    glfwMakeContextCurrent(window);
    glfwSwapInterval(1); // vsync

    // Callbacks
    glfwSetKeyCallback(window, key_callback);
    glfwSetMouseButtonCallback(window, mouse_button_callback);
    glfwSetCursorPosCallback(window, cursor_pos_callback);
    glfwSetScrollCallback(window, scroll_callback);
    glfwSetFramebufferSizeCallback(window, framebuffer_size_callback);

    // Retina display: use framebuffer size
    glfwGetFramebufferSize(window, &g_fb_width, &g_fb_height);
    glViewport(0, 0, g_fb_width, g_fb_height);

    // Print GL info
    std::cout << "OpenGL: " << glGetString(GL_VERSION) << std::endl;

    // Fetch simulation data from backend
    g_sim = fetch_simulation("http://localhost:5001/api/banking/simulate");
    if (!g_sim.loaded) {
        std::cerr << "Failed to load simulation data. Exiting." << std::endl;
        glfwTerminate();
        return 1;
    }

    // Init renderer
    g_renderer.init();

    // Main loop
    float last_time = (float)glfwGetTime();

    while (!glfwWindowShouldClose(window)) {
        float now = (float)glfwGetTime();
        float dt = now - last_time;
        last_time = now;
        g_time += dt;

        // Auto-play
        if (g_auto_play) {
            g_auto_timer += dt;
            if (g_auto_timer >= g_auto_interval) {
                g_auto_timer = 0.0f;
                advance_round();
            }
        }

        g_cam.update(dt);

        glfwGetFramebufferSize(window, &g_fb_width, &g_fb_height);
        glViewport(0, 0, g_fb_width, g_fb_height);
        glClearColor(0.06f, 0.07f, 0.10f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        // Draw 3D scene
        g_renderer.draw_scene(g_sim, g_cam, g_current_round, g_time,
                              g_affected, g_active_edges,
                              g_fb_width, g_fb_height);

        // Draw HUD
        float cum_loss = 0.0f;
        int stressed = 0, failed = 0;
        std::string label = "Pre-Shock";
        if (g_current_round >= 0 && g_current_round < (int)g_sim.rounds.size()) {
            auto& r = g_sim.rounds[g_current_round];
            cum_loss = r.cumulative_loss;
            stressed = r.banks_stressed;
            failed = r.banks_failed;
            label = r.label;
        }

        g_renderer.draw_hud(g_current_round, label, cum_loss,
                            stressed, failed, g_auto_play,
                            (int)g_sim.rounds.size(),
                            g_fb_width, g_fb_height);

        glfwSwapBuffers(window);
        glfwPollEvents();
    }

    glfwTerminate();
    return 0;
}
