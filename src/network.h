#pragma once
#include <string>
#include <vector>
#include <map>
#include <set>
#include <glm/glm.hpp>

struct BankNode {
    std::string id;
    std::string name;       // short_name from API
    std::string type;       // "central_bank", "g_sib", etc.
    std::string country;
    std::string status;     // "normal", "stressed", "critical", "failed", "resolution"
    float total_assets = 0;
    float cet1_ratio_pct = 0;
    float lcr_pct = 0;
    float credit_spread_bps = 0;
    glm::vec3 position{0};
    float radius = 0.3f;
};

struct NetworkEdge {
    std::string source;
    std::string target;
    float amount = 0;
    bool is_secured = false;
};

struct ContagionEdge {
    std::string source;
    std::string target;
};

struct RoundState {
    int round_num = 0;
    std::string label;
    std::map<std::string, BankNode> bank_states;
    std::vector<ContagionEdge> active_edges;
    std::vector<std::string> affected_banks;
    float round_loss = 0;
    float cumulative_loss = 0;
    int banks_stressed = 0;
    int banks_failed = 0;
    int banks_normal = 0;
};

struct SimulationData {
    std::vector<BankNode> nodes;
    std::vector<NetworkEdge> edges;
    std::vector<RoundState> rounds;
    std::map<std::string, int> node_index;
    bool loaded = false;
    std::string error;
};

// Fetch JSON from the AGORA backend and parse into SimulationData
SimulationData fetch_simulation(const std::string& url);
