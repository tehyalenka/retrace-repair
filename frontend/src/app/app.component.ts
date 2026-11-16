import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./app.component.html'})
export class AppComponent implements OnInit,OnDestroy {
  pages=['Overview','Repository','Agent Workspace','Runs & Diffs','Retrieval Lab','Benchmarks','Settings'];
  icons=['◫','⌘','✧','⑂','◎','▥','⚙'];
  page='Overview'; repo='.'; repos:string[]=['.']; task='Implement a robust feature with tests'; strategy='dependency'; attempts=2; maxFiles=6; generateTests=false;
  health:any=null; inventory:any=null; selectedFile=''; source=''; retrieval:any=null; runs:any[]=[]; activeRun:any=null; diffs:any={}; reports:any[]=[];
  busy=false; error=''; notice=''; timer:any=null; demo=false;
  constructor(private http:HttpClient){}
  ngOnInit(){this.refresh();this.timer=setInterval(()=>this.poll(),3000);}
  ngOnDestroy(){clearInterval(this.timer);}
  api(path:string){return '/api'+path;}
  fail(e:any){this.error=e?.error?.detail||e?.message||'Request failed';this.busy=false;}
  refresh(){this.http.get<any>(this.api('/health')).subscribe({next:v=>this.health=v,error:()=>{this.demo=true;this.error='Backend offline. Start FastAPI to enable live features.'}});
    this.http.get<any>(this.api('/repositories')).subscribe({next:v=>this.repos=v.repositories,error:()=>{}});
    this.http.get<any>(this.api('/benchmarks')).subscribe({next:v=>this.reports=v.reports,error:()=>{}});
    this.poll();}
  poll(){this.http.get<any>(this.api('/runs')).subscribe({next:v=>{this.runs=v.runs;if(this.activeRun){this.http.get<any>(this.api('/runs/'+this.activeRun.id)).subscribe({next:r=>this.activeRun=r,error:()=>{}});}},error:()=>{}});}
  selectPage(page:string){this.page=page;this.error='';if(page==='Repository')this.loadRepo();}
  loadRepo(){this.busy=true;this.http.post<any>(this.api('/repository'),{repository:this.repo}).subscribe({next:v=>{this.inventory=v;this.busy=false;this.selectedFile='';this.source='';},error:e=>this.fail(e)});}
  openFile(path:string){this.selectedFile=path;this.http.get<any>(this.api('/file'),{params:{repository:this.repo,path}}).subscribe({next:v=>this.source=v.content,error:e=>this.fail(e)});}
  analyze(){this.busy=true;this.retrieval=null;this.http.post<any>(this.api('/retrieval'),{repository:this.repo,task:this.task,max_files:this.maxFiles,strategy:this.strategy}).subscribe({next:v=>{this.retrieval=v;this.busy=false;},error:e=>this.fail(e)});}
  startRun(){if(!confirm('Run the agent on a trusted repository? This may execute repository tests and make paid or rate-limited LLM calls. The original repository is not edited.'))return;
    this.busy=true;this.http.post<any>(this.api('/runs'),{repository:this.repo,task:this.task,max_files:this.maxFiles,strategy:this.strategy,attempts:this.attempts,generate_tests:this.generateTests}).subscribe({next:v=>{this.busy=false;this.notice='Agent started';this.activeRun=v;this.page='Runs & Diffs';this.poll();},error:e=>this.fail(e)});}
  selectRun(id:string){
    this.diffs={};
    this.verificationResult=null;
    this.artifactAvailable=false;
    this.artifactMessage='';
    this.http.get<any>(this.api('/runs/'+id)).subscribe({
      next:v=>{
        this.activeRun=v;
        this.page='Runs & Diffs';
        if(v.status==='completed'){
          this.loadDiff(id);
          this.checkArtifacts(id);
        }
      },
      error:e=>this.fail(e)
    });
  }
  loadDiff(id:string){this.http.get<any>(this.api('/diff/'+id)).subscribe({next:v=>this.diffs=v.diffs,error:e=>this.fail(e)});}

  artifactAvailable = false;
  artifactChecking = false;
  verificationBusy = false;
  downloadBusy = false;
  verificationResult: any = null;
  artifactMessage = '';


  checkArtifacts(id: string) {
    this.artifactChecking = true;
    this.artifactAvailable = false;
    this.artifactMessage = '';

    this.http.get<any>(this.api('/artifacts/' + id)).subscribe({
      next: data => {
        if (this.activeRun?.id !== id) return;
        this.artifactChecking = false;
        this.artifactAvailable = true;
        this.artifactMessage =
          (data.generated_files?.length || 0) + ' generated file(s) saved';
      },
      error: e => {
        if (this.activeRun?.id !== id) return;
        this.artifactChecking = false;
        this.artifactAvailable = false;
        this.artifactMessage = e.status === 404
          ? 'No saved artifacts for this run.'
          : 'Could not check saved artifacts.';
      }
    });
  }

  verifySavedRun(id: string) {
    if (!this.artifactAvailable || this.verificationBusy) return;

    if (!confirm(
      'Run independent tests on this trusted repository? ' +
      'This executes local Python code without a security sandbox.'
    )) return;

    this.verificationBusy = true;
    this.verificationResult = null;
    this.error = '';

    this.http.post<any>(
      this.api('/artifacts/' + id + '/verify'), {}
    ).subscribe({
      next: result => {
        if (this.activeRun?.id !== id) return;
        this.verificationBusy = false;
        this.verificationResult = result;
      },
      error: e => {
        if (this.activeRun?.id !== id) return;
        this.verificationBusy = false;
        this.error = e?.error?.detail ||
          e?.message || 'Independent verification failed';
      }
    });
  }

  downloadGeneratedCode(id: string) {
    if (!this.artifactAvailable || this.downloadBusy) return;

    this.downloadBusy = true;
    this.error = '';

    this.http.get(
      this.api('/artifacts/' + id + '/download'),
      { responseType: 'blob' }
    ).subscribe({
      next: blob => {
        this.downloadBusy = false;

        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');

        anchor.href = url;
        anchor.download = 'codepilot-' + id + '.zip';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);
      },
      error: e => {
        this.downloadBusy = false;
        this.error = e?.message || 'Artifact download failed';
      }
    });
  }

  keys(value:any){return Object.keys(value||{});}
  percent(value:any){return typeof value==='number'?(value*100).toFixed(1)+'%':'—';}
  pretty(value:any){return JSON.stringify(value,null,2);}
  isRunReport(report:any):boolean {
    return typeof report?.data?.run_id === 'string';
  }

  isBaselineReport(report:any):boolean {
    return !!report?.data?.reference_solution &&
           !!report?.data?.baseline;
  }

  benchmarkOutcome(report:any):string {
    const outcome = report?.data?.outcome;

    const labels:Record<string,string> = {
      independent_verification_passed: 'Independent verification passed',
      independent_verification_failed: 'Independent verification failed',
      smoke_tests_passed: 'Smoke tests passed',
      reported_success_unverified: 'Success reported; evidence incomplete',
      provider_failure: 'Provider failure',
      agent_test_failure: 'Agent test failure',
      agent_failure: 'Agent failure',
      not_evaluated: 'Not evaluated'
    };

    return labels[outcome] || 'Not classified';
  }

  benchmarkProvenance(report:any):string {
    const provenance = report?.data?.execution_provenance;

    if (
      provenance?.source === 'codepilot_agent' &&
      provenance?.execution_mode === 'autonomous' &&
      provenance?.recorded_at_creation === true
    ) {
      return 'Agent execution recorded';
    }

    return 'Not established';
  }

  benchmarkTestCount(output:any):string {
    if (typeof output !== 'string') return 'Not recorded';

    const match = output.match(/Ran (\d+) tests?/);

    return match ? match[1] + ' tests executed' : 'Count unavailable';
  }

  reportSummary(report:any){return report?.data?.summary||report?.data?.aggregate||report?.data?.metrics||null;}
}
