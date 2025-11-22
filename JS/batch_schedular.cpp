#include <arpa/inet.h>
#include <unistd.h>
#include <vector>
#include <chrono>
#include <iostream>
#include <random>
#include <algorithm>

using namespace std;
using namespace chrono;

struct Worker { string ip; int port; };

int send_rpc(string ip, int port, string msg, string &reply) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    if (connect(sock, (sockaddr*)&addr, sizeof(addr)) < 0)
        return -1;

    msg += "\n";
    write(sock, msg.c_str(), msg.size());

    char buf[1024];
    int n = read(sock, buf, 1023);
    if (n <= 0) { close(sock); return -2; }
    buf[n] = 0;
    reply = buf;
    close(sock);
    return 0;
}

int main() {
    vector<Worker> workers = {
        {"10.96.1.135", 9100},   // Worker VM 1
        {"10.96.1.136", 9100}    // Worker VM 2
    };

    int jobs = 100;   // simulate 100 jobs
    int probe_ratio = 2;
    int tasks_per_job = 3;

    long total_wait = 0;
    long total_service = 0;
    long total_response = 0;
    long total_rpc = 0;

    random_device rd;
    mt19937 rng(rd());

    for (int j = 0; j < jobs; j++) {
        bool heavy = (rand() % 10 == 0);  // 10% heavy jobs
        int dur = heavy ? 400 : 30;

        auto start = high_resolution_clock::now();

        // batch sample
        vector<pair<int,int>> qvec;  // (worker_idx, queue_len)

        for (int i = 0; i < workers.size(); i++) {
            string reply;
            send_rpc(workers[i].ip, workers[i].port, "PROBE", reply);
            int q = atoi(reply.substr(2).c_str());
            qvec.push_back({i,q});
            total_rpc++;
        }

        sort(qvec.begin(), qvec.end(), [](auto &a, auto &b){
            return a.second < b.second;
        });

        // assign tasks
        for (int t = 0; t < tasks_per_job; t++) {
            string reply;
            send_rpc(workers[qvec[t % workers.size()].first].ip,
                     workers[qvec[t % workers.size()].first].port,
                     "ASSIGN " + to_string(dur), reply);
            total_rpc++;
        }

        auto end = high_resolution_clock::now();
        long response = duration_cast<milliseconds>(end - start).count();

        total_response += response;
        total_service  += dur;
        total_wait     += (response - dur);
    }

    cout << "\n=== Batch Sampling Results ===\n";
    cout << "Avg wait time: " << total_wait / jobs << " ms\n";
    cout << "Avg service time: " << total_service / jobs << " ms\n";
    cout << "Avg response time: " << total_response / jobs << " ms\n";
    cout << "Avg RPCs per job: " << total_rpc / jobs << "\n";

    return 0;
}
