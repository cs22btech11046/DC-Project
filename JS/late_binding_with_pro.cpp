#include <arpa/inet.h>
#include <unistd.h>
#include <vector>
#include <chrono>
#include <iostream>
using namespace std;
using namespace chrono;

struct Worker { string ip; int port; };

int rpc(string ip,int port,string msg,string&reply){
    int s=socket(AF_INET,SOCK_STREAM,0);
    sockaddr_in a{};a.sin_family=AF_INET;a.sin_port=htons(port);
    inet_pton(AF_INET,ip.c_str(),&a.sin_addr);
    if(connect(s,(sockaddr*)&a,sizeof(a))<0) return -1;
    msg+="\n"; write(s,msg.c_str(),msg.size());
    char buf[1024];int n=read(s,buf,1023);
    if(n>0){buf[n]=0;reply=buf;}
    close(s);return 0;
}

int main(){
    vector<Worker>W={
        {"10.96.1.135",9100},
        {"10.96.1.136",9100}
    };

    int jobs=100;
    long total_wait=0,total_serv=0,total_resp=0,total_rpc=0;

    for(int j=0;j<jobs;j++){
        bool heavy=(rand()%10==0);
        int dur=heavy?400:30;

        auto t0=high_resolution_clock::now();

        // REQUEST to workers
        for(auto&w:W){
            string r;
            rpc(w.ip,w.port,"REQUEST "+to_string(dur),r);
            total_rpc++;
        }

        // proactive cancellation (assuming only 1 task needed)
        for(auto&w:W){
            string r;
            rpc(w.ip,w.port,"CANCEL",r);
            total_rpc++;
        }

        auto t1=high_resolution_clock::now();
        long resp=duration_cast<milliseconds>(t1-t0).count();

        total_resp+=resp;
        total_serv+=dur;
        total_wait+=(resp-dur);
    }

    cout<<"\n=== Late Binding + Proactive Cancel ===\n";
    cout<<"Avg wait: "<<total_wait/jobs<<" ms\n";
    cout<<"Avg service: "<<total_serv/jobs<<" ms\n";
    cout<<"Avg response: "<<total_resp/jobs<<" ms\n";
    cout<<"Avg RPC/job: "<<total_rpc/jobs<<"\n";
}
