#include <arpa/inet.h>
#include <thread>
#include <mutex>
#include <atomic>
#include <map>
#include <unistd.h>
#include <iostream>
#include <sstream>
#include <chrono>

using namespace std;

atomic<int> queue_len(0);
mutex mtx;

void execute_task(int duration_ms) {
    this_thread::sleep_for(chrono::milliseconds(duration_ms));
    queue_len--;
}

void handle_client(int sock) {
    char buf[1024];
    int n = read(sock, buf, 1023);
    if (n <= 0) { close(sock); return; }
    buf[n] = 0;
    string req = buf;

    string cmd;
    stringstream ss(req);
    ss >> cmd;

    if (cmd == "PROBE") {
        string msg = "Q " + to_string(queue_len.load()) + "\n";
        write(sock, msg.c_str(), msg.size());
    }
    else if (cmd == "ASSIGN") {
        int dur = 0;
        ss >> dur;
        queue_len++;
        thread(execute_task, dur).detach();
        string msg = "OK\n";
        write(sock, msg.c_str(), msg.size());
    }
    else if (cmd == "CANCEL") {
        string msg = "CANCELLED\n";
        write(sock, msg.c_str(), msg.size());
    }
    else if (cmd == "REQUEST") {  
        // Late binding request reply
        int dur;
        ss >> dur;
        queue_len++;
        thread(execute_task, dur).detach();
        string msg = "START\n";
        write(sock, msg.c_str(), msg.size());
    }
    close(sock);
}

int main(int argc, char** argv) {
    int port = 9100;
    if (argc >= 2) port = stoi(argv[1]);

    int server = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    bind(server, (sockaddr*)&addr, sizeof(addr));
    listen(server, 50);

    cout << "[worker] Listening on " << port << endl;

    while (true) {
        sockaddr_in client;
        socklen_t len = sizeof(client);
        int sock = accept(server, (sockaddr*)&client, &len);
        thread(handle_client, sock).detach();
    }
    return 0;
}
