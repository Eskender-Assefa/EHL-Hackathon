let csrf = '';
export function setCsrf(value) { csrf = value; }
export async function api(path, {method='GET', body, signal}={}) {
  let response;
  try {response=await fetch(`/api/v1${path}`,{method,signal,headers:body?{'Content-Type':'application/json','X-BMW-CSRF':csrf}:{},body:body?JSON.stringify(body):undefined,credentials:'same-origin'});}
  catch(error){if(error.name==='AbortError')throw error;throw new Error('Cannot reach the local API. Check the server, then Refresh.');}
  const result=await response.json().catch(()=>({}));
  if(!response.ok){const details=result.error;const message=typeof details?.message==='string'?details.message:details?.message?.message;
    const error=new Error(message || (response.status===503?'Database unavailable. Retry after checking the local database.':`Request failed (${response.status})`));
    error.status=response.status;error.result=result;
    if(details?.issues)error.message+='\n'+details.issues.map(x=>`${x.field}: ${x.message}`).join('\n');throw error;}
  return result;
}
