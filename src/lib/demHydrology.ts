/** Exploratory D8 routing on a sampled DEM. No sink filling, stream burning or calibration. */
export function analyzeD8(values:ArrayLike<number>,width:number,height:number,nodata:number|null){
 const n=width*height;
 const downstream=new Int32Array(n).fill(-1);
 const accumulation=new Uint32Array(n).fill(1);
 const indegree=new Uint8Array(n);
 const valid=(i:number)=>Number.isFinite(Number(values[i]))&&(nodata===null||Number(values[i])!==nodata);
 const neighbors=[[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
 let count=0,sinks=0;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const i=y*width+x;if(!valid(i))continue;count++;
  let best=-1,steepest=0;
  for(const [dy,dx] of neighbors){
   const yy=y+dy,xx=x+dx;if(yy<0||xx<0||yy>=height||xx>=width)continue;
   const j=yy*width+xx;if(!valid(j))continue;
   const slope=(Number(values[i])-Number(values[j]))/(dx&&dy?Math.SQRT2:1);
   if(slope>steepest){steepest=slope;best=j}
  }
  downstream[i]=best;if(best<0)sinks++;else indegree[best]++;
 }
 const queue=new Int32Array(n);let head=0,tail=0;
 for(let i=0;i<n;i++)if(valid(i)&&indegree[i]===0)queue[tail++]=i;
 let maxAccumulation=0;
 while(head<tail){
  const i=queue[head++],j=downstream[i];
  if(accumulation[i]>maxAccumulation)maxAccumulation=accumulation[i];
  if(j>=0){accumulation[j]+=accumulation[i];if(--indegree[j]===0)queue[tail++]=j}
 }
 let drainagePixels=0;const cutoff=Math.max(20,Math.ceil(count*.002));
 for(let i=0;i<n;i++)if(valid(i)&&accumulation[i]>=cutoff)drainagePixels++;
 return {validPixels:count,sinks,maxAccumulation,drainagePixels,cutoff};
}
