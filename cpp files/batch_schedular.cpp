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
    if (sock < 0) return -1;

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    if (connect(sock, (sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sock);
        return -1;
    }

    msg += "\n";
    write(sock, msg.c_str(), msg.size());

    char buf[1024];
    int n = read(sock, buf, 1023);
    if (n <= 0) {
        close(sock);
        return -2;
    }

    buf[n] = 0;
    reply = buf;
    close(sock);
    return 0;
}

int main() {
    // TODO: Change this to the IP of the scheduler VM
    string myIP = "10.96.1.125";

    vector<Worker> workers = {
        {"10.96.1.163", 9100},
        {"10.96.1.158", 9100},
        {"10.96.0.170", 9100},
        {"10.96.1.206", 9100},
        {"10.96.0.214", 9100},
        {"10.96.1.145", 9100}
    };

    int jobs = 10;
    int tasks_per_job = 3;

    long total_wait = 0;
    long total_service = 0;
    long total_response = 0;
    long total_rpc = 0;

    for (int j = 0; j < jobs; j++) {

        bool heavy = (rand() % 10 == 0);
        int dur = heavy ? 400 : 30;

        auto start = high_resolution_clock::now();

        // batch sampling
        vector<pair<int,int>> qvec;

        for (int i = 0; i < workers.size(); i++) {

            string reply;
            int status = send_rpc(workers[i].ip, workers[i].port, "PROBE", reply);
            total_rpc++;

            int q = 9999; // unreachable worker treated as high load

            if (status == 0 && reply.size() >= 3 && reply[0] == 'Q') {
                // safe parsing: "Q <num>"
                string num = reply.substr(2);
                try { q = stoi(num); }
                catch (...) { q = 9999; }
            }

            qvec.push_back({i, q});
        }

        // sort by queue length
        sort(qvec.begin(), qvec.end(),
            [](auto &a, auto &b){ return a.second < b.second; });

        // assign tasks to least loaded workers
        for (int t = 0; t < tasks_per_job; t++) {

            int idx = qvec[t % workers.size()].first;
            string reply;

            string msg = "ASSIGN " + to_string(dur) + " " + myIP;

            send_rpc(workers[idx].ip, workers[idx].port, msg, reply);
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
