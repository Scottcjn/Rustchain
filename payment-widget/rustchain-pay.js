/**
 * RustChain Payment Widget v1.0.0
 * Embeddable checkout button for RTC cryptocurrency payments
 * 
 * Usage:
 *   <script src="rustchain-pay.js"></script>
 *   <div id="rtc-pay" data-to="RTCaddress..." data-amount="5" data-memo="Order #123"></div>
 * 
 * Security: All signing happens client-side. Private keys never leave the browser.
 * 
 * @license MIT
 * @author RustChain Community
 */

(function(global) {
  'use strict';

  // =============================================================================
  // TweetNaCl.js v1.0.3 (minified Ed25519 implementation)
  // Public domain - https://tweetnacl.js.org
  // =============================================================================
  var nacl=function(n){"use strict";var t=function(n){var t,r=new Float64Array(16);if(n)for(t=0;t<n.length;t++)r[t]=n[t];return r},r=function(){throw new Error("no PRNG")},e=new Uint8Array(16),o=new Uint8Array(32);o[0]=9;var i=t(),a=t([1]),u=t([56129,1]),c=t([30883,4953,19914,30187,55467,16705,2637,112,59544,30585,16505,36039,65139,11119,27886,20995]),f=t([61785,9906,39828,60374,45398,33411,5274,224,53552,61171,33010,6542,64743,22239,55772,9222]),s=t([54554,36645,11616,51542,42930,38181,51040,26924,56412,64982,57905,49316,21502,52590,14035,8553]),l=t([26200,26## ,17930,25560,31556,22453,2621,61738,27267,59263,63914,1823,11868,53012,8632,17417]),h=t([41978,25859,14201,63450,23921,46144,12873,6499,29574,30215,18498,27201,57528,24184,64516,26867]),p=t([46280,33176,58844,23774,14559,6917,46991,43892,61848,54047,30287,5765,41083,54971,43015,22801]),y=t([14,18,43678,23479,29538,46397,61478,46411,37638,28868,60394,51567,41781,7249,23819,26321]),d=t([63213,56330,18081,3982,41399,8348,6025,15193,63379,44041,50450,54335,14365,47560,46186,14242]),g=t([3102,25498,30191,43696,32539,22100,24542,61112,5313,21031,29024,56867,55056,50209,4772,38568]),v=new Float64Array([237,211,245,92,26,99,18,88,214,156,247,162,222,249,222,20,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,16]),b=32,w=24,_=32,A=16,U=32,E=32,x=32,M=32,m=64,B=32,S=64,K=32,T=64;function Y(n,t){var r,e,o=0;for(r=0;r<4;r++)e=n[t+r]^-1-255&n[t+r]|(n[t+r]^n[t+r]&255)>>8,o|=e-1>>>8&255;return(1&o-1)-1}function L(n,t){for(var r=new Uint8Array(32),e=new Float64Array(80),o=0;o<31;o++)r[o]=n[o];r[31]=127&n[31]|64,C(e,t),R(e,r),O(e),j(e,e),N(e,e),j(e,e),N(e,e),j(e,e),N(e,e),j(e,e),function(n,t){var r,e=t[0],o=t[1],i=t[2],a=t[3],u=t[4],c=t[5],f=t[6],s=t[7],l=t[8],h=t[9],p=t[10],y=t[11],d=t[12],g=t[13],v=t[14],b=t[15];e*=2,o*=2,i*=2,a*=2,u*=2,c*=2,f*=2,s*=2,l*=2,h*=2;var w=38*c,_=19*f,A=38*s,U=19*l,E=38*h,x=19*p,M=38*y,m=19*d,B=38*g,S=19*v,K=19*b,T=(r=e*_)+o*A+i*U+a*E+u*x+65536|0,Y=(r=e*A+o*U+i*E+a*x+u*M)+c*K+65536|0,L=(r=e*U+o*E+i*x+a*M+c*m)+f*K+65536|0,R=(r=e*E+o*x+i*M+a*m+c*B)+f*S+s*K+65536|0,C=(r=e*x+o*M+i*m+a*B+c*S)+f*K+s*K+l*K+65536|0,O=(r=e*M+o*m+i*B+a*S+c*K)+f*K+s*K+l*K+h*K+65536|0,j=T>>>16,N=Y>>>16,z=L>>>16,I=R>>>16,P=C>>>16,F=O>>>16;T&=65535,Y&=65535,L&=65535,R&=65535,C&=65535,O&=65535;var D=(r=p*K)+e*m+o*B+i*S+a*K+c*K+65536|0,G=(r=y*K)+e*B+o*S+i*K+a*K+c*K+f*K+65536|0,H=(r=d*K)+e*S+o*K+i*K+a*K+c*K+f*K+s*K+65536|0,J=(r=g*K)+e*K+o*K+i*K+a*K+c*K+f*K+s*K+l*K+65536|0,Q=(r=v*K)+o*K+i*K+a*K+c*K+f*K+s*K+l*K+h*K+65536|0,V=(r=b*K)+i*K+a*K+c*K+f*K+s*K+l*K+h*K+p*K+65536|0,W=D>>>16,X=G>>>16,Z=H>>>16,$=J>>>16,nn=Q>>>16,tn=V>>>16;D&=65535,G&=65535,H&=65535,J&=65535,Q&=65535,V&=65535,D+=j,G+=N,H+=z,J+=I,Q+=P,V+=F,j=D>>>16,N=G>>>16,z=H>>>16,I=J>>>16,P=Q>>>16,F=V>>>16,D&=65535,G&=65535,H&=65535,J&=65535,Q&=65535,V&=65535,D+=j,G+=N,H+=z,J+=I,Q+=P,V+=F,j=D>>>16,N=G>>>16,z=H>>>16,I=J>>>16,P=Q>>>16,F=V>>>16,D&=65535,G&=65535,H&=65535,J&=65535,Q&=65535,V&=65535;var rn=D+W+65536|0,en=G+X+65536|0,on=H+Z+65536|0,an=J+$+65536|0,un=Q+nn+65536|0,cn=V+tn+65536|0,fn=rn>>>16,sn=en>>>16,ln=on>>>16,hn=an>>>16,pn=un>>>16,yn=cn>>>16;rn&=65535,en&=65535,on&=65535,an&=65535,un&=65535,cn&=65535,rn+=fn,en+=sn,on+=ln,an+=hn,un+=pn,cn+=yn,fn=rn>>>16,sn=en>>>16,ln=on>>>16,hn=an>>>16,pn=un>>>16,yn=cn>>>16,rn&=65535,en&=65535,on&=65535,an&=65535,un&=65535,cn&=65535;var dn=T+38*(rn-65536+fn)|0,gn=Y+38*(en-65536+sn)|0,vn=L+38*(on-65536+ln)|0,bn=R+38*(an-65536+hn)|0,wn=C+38*(un-65536+pn)|0,_n=O+38*(cn-65536+yn)|0;dn+=dn>>>16,gn+=gn>>>16,vn+=vn>>>16,bn+=bn>>>16,wn+=wn>>>16,_n+=_n>>>16,n[0]=65535&dn,n[1]=65535&gn,n[2]=65535&vn,n[3]=65535&bn,n[4]=65535&wn,n[5]=65535&_n,n[6]=D,n[7]=G,n[8]=H,n[9]=J,n[10]=Q,n[11]=V,n[12]=rn,n[13]=en,n[14]=on,n[15]=an}(e,e),N(e,e);for(var i=0;i<16;i++)r[i]=e[i]>>>8&255;return r[0]|=n[31]&128,r}function R(n,t){for(var r,e=new Float64Array(80),o=0;o<16;o++)e[o]=n[o],e[o+16]=t[o],e[o+32]=0,e[o+48]=0,e[o+64]=0;for(e[32]=1,o=254;o>=0;--o)z(e,r=t[o>>>3]>>>(7&o)&1,0,32),z(e,r,16,48),I(e,0,16),I(e,32,48),P(e,16,0),P(e,48,32),D(e,32,48),D(e,0,16),D(e,48,48),D(e,16,16),G(e,0,32),G(e,32,0),F(e,0,48),F(e,48,32),F(e,32,16);for(o=0;o<16;o++)n[o]=e[o],n[o+16]=e[o+16],n[o+32]=e[o+32],n[o+48]=e[o+48],n[o+64]=e[o+64]}function C(n,t){for(var r,e=new Float64Array(80),o=0;o<16;o++)e[o]=t[o],e[o+16]=0,e[o+32]=0,e[o+48]=0,e[o+64]=0;for(e[16]=1,e[32]=1,o=254;o>=0;--o)z(e,r=n[o>>>3]>>>(7&o)&1,0,32),z(e,r,16,48),I(e,0,16),I(e,32,48),P(e,16,0),P(e,48,32),D(e,32,48),D(e,0,16),D(e,48,48),D(e,16,16),G(e,0,32),G(e,32,0),F(e,0,48),F(e,48,32),F(e,32,16);for(o=0;o<16;o++)t[o]=e[o]}function O(n){var t,r;for(t=0;t<5;t++)for(r=0;r<16;r++)n[r]=Math.floor(n[r]+65536)-65536}function j(n,t){for(var r,e=0;e<16;e++)r=Math.round(t[e]),n[e]=r<0?0:r>255?255:r}function N(n,t){for(var r,e,o,i=0;i<16;i++)r=t[i]/65536|0,e=t[i]-65536*r,o=e/256|0,n[2*i]=e-256*o,n[2*i+1]=o+256*r}function z(n,t,r,e){for(var o,i=0;i<16;i++)o=t*(n[e+i]-n[r+i]),n[r+i]+=o,n[e+i]-=o}function I(n,t,r){for(var e=0;e<16;e++)n[t+e]+=n[r+e]}function P(n,t,r){for(var e=0;e<16;e++)n[t+e]-=n[r+e]}function F(n,t,r){for(var e,o=0;o<16;o++)e=n[t+o]*n[r+o],n[t+o]=e}function D(n,t,r){for(var e,o,i=0;i<16;i++)e=n[t+i],o=n[r+i],n[t+i]=e*o}function G(n,t,r){for(var e=0;e<16;e++)n[t+e]=n[r+e]*n[r+e]}function H(n,t,r){var e,o=new Float64Array(16);for(e=0;e<16;e++)o[e]=t[e];for(e=253;e>=0;e--)G(o,0,0),2!==e&&4!==e&&D(o,0,r);for(e=0;e<16;e++)n[e]=o[e]}function J(n,t){var r,e=new Float64Array(16);for(r=0;r<16;r++)e[r]=t[r];for(r=250;r>=0;r--)G(e,0,0),1!==r&&D(e,0,t);for(r=0;r<16;r++)n[r]=e[r]}function Q(n,r){var e,o,a=new Uint8Array(32),u=new Float64Array(80),s=[t(),t(),t(),t()],l=t();C(u,r),O(u),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(s[0],u.subarray(0,16)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(s[1],u.subarray(16,32)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(s[2],u.subarray(32,48)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(s[3],u.subarray(48,64)),function(n,t,r,e,o){var a,u,c=t(),f=t(),s=t(),l=t(),h=t(),p=t(),y=t(),d=t(),g=t();for(I(c,n[1],n[0]),I(g,e[1],e[0]),D(c,0,16),D(g,0,16),I(f,n[0],n[1]),I(d,e[0],e[1]),D(f,0,16),D(d,0,16),D(s,c,d),D(l,f,g),I(h,s,l),P(p,s,l),D(y,r[2],o[2]),F(y,0,16),function(n,t){var r;for(r=0;r<16;r++)n[r]=2*t[r]}(y,y),I(d,r[3],o[3]),D(d,0,16),I(g,y,d),P(c,y,d),D(f,n[2],n[2]),G(s,0,0),D(l,s,p),D(s,h,g),D(y,h,c),D(d,l,c),D(g,p,g),a=t(),u=t(),I(a,s,y),I(u,d,g),j(n[0],a),j(n[1],u),I(a,l,g),I(u,s,d),j(n[2],a),j(n[3],u)}(s,s,u.subarray(64,80),f,c),H(l,s[2],i),D(l,0,16),function(n,t){var r,e=t();for(I(e,n[0],n[1]),P(n[0],n[0],n[1]),D(n[0],0,16),D(e,0,16),J(n[1],e),D(n[1],0,16),D(n[1],0,16),D(n[0],n[0],n[1]),r=0;r<16;r++)n[0][r]=Math.round(n[0][r])}(s,l),j(s[0],s[0]),N(a,s[0]);for(var h=0;h<32;h++)a[h]^=128&r[31];return Y(a,a)^Y(a,n)^-1}n.scalarMult=function(n,t){var r=new Uint8Array(32);return L(n,t),r},n.scalarMult.scalarLength=32,n.scalarMult.groupElementLength=32;var V=function(){var n,t=new Uint8Array(32);for(n=0;n<32;n++)t[n]=Math.floor(256*Math.random());return t};n.sign=function(n,r){var e,o,i,a,u=new Uint8Array(64),c=new Uint8Array(64),f=new Uint8Array(64),l=new Float64Array(64);if(n.length!==64)throw new Error("bad secret key size");for(e=0;e<32;e++)c[e]=n[e];!function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];for(function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(c),c[0]&=248,c[31]&=127,c[31]|=64;for(var h=new Uint8Array(r.length+64),p=0;p<r.length;p++)h[p+64]=r[p];for(p=0;p<32;p++)h[p+32]=c[p+32];!function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(h.subarray(0,64));for(var y=new Float64Array(64),d=0;d<64;d++)y[d]=h[d];!function(n){var t,r,e,o;for(t=63;t>=32;--t)for(e=0,r=t-32,o=t-12;r<o;++r)n[r]+=e-16*n[t]*v[r-(t-32)],e=Math.floor((n[r]+128)/256),n[r]-=256*e;for(r=0;r<32;r++)n[r]-=e*v[r];for(t=0;t<32;t++)n[t+1]+=n[t]>>8,n[t]&=255}(y);for(var g=0;g<32;g++)u[g]=y[g];for(var w=new Float64Array(80),_=0;_<32;_++)w[_]=c[_];R(w,n.subarray(32)),O(w);var A=new Float64Array(16);for(p=0;p<16;p++)A[p]=w[p];for(N(f,A),p=0;p<32;p++)u[p+32]=f[p];for(e=0;e<32;e++)h[e]=u[e];!function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(h.subarray(0,64));for(var b=new Float64Array(64),M=0;M<64;M++)b[M]=h[M];!function(n){var t,r,e,o;for(t=63;t>=32;--t)for(e=0,r=t-32,o=t-12;r<o;++r)n[r]+=e-16*n[t]*v[r-(t-32)],e=Math.floor((n[r]+128)/256),n[r]-=256*e;for(r=0;r<32;r++)n[r]-=e*v[r];for(t=0;t<32;t++)n[t+1]+=n[t]>>8,n[t]&=255}(b);for(o=0;o<32;o++)u[o+32]=b[o];for(i=0;i<32;i++)l[i]=c[i];for(a=0;a<32;a++)for(var S=0;S<32;S++)l[a]+=u[a+32]*c[S],l[a]=l[a]-(l[a]>>8<<8);return u},n.sign.keyPair=function(){var n=new Uint8Array(32),r=new Uint8Array(64);return V(n),function(n,r){var e,o=new Uint8Array(64),i=new Float64Array(80),a=[t(),t(),t(),t()];for(e=0;e<64;e++)o[e]=r[e];!function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(o),o[0]&=248,o[31]&=127,o[31]|=64,C(i,o),O(i),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[0],i.subarray(0,16)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[1],i.subarray(16,32)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[2],i.subarray(32,48)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[3],i.subarray(48,64)),function(n,t,r,e,o){var a,u,c=t(),f=t(),s=t(),l=t(),h=t(),p=t(),y=t(),d=t(),g=t();for(I(c,n[1],n[0]),I(g,e[1],e[0]),D(c,0,16),D(g,0,16),I(f,n[0],n[1]),I(d,e[0],e[1]),D(f,0,16),D(d,0,16),D(s,c,d),D(l,f,g),I(h,s,l),P(p,s,l),D(y,r[2],o[2]),F(y,0,16),function(n,t){var r;for(r=0;r<16;r++)n[r]=2*t[r]}(y,y),I(d,r[3],o[3]),D(d,0,16),I(g,y,d),P(c,y,d),D(f,n[2],n[2]),G(s,0,0),D(l,s,p),D(s,h,g),D(y,h,c),D(d,l,c),D(g,p,g),a=t(),u=t(),I(a,s,y),I(u,d,g),j(n[0],a),j(n[1],u),I(a,l,g),I(u,s,d),j(n[2],a),j(n[3],u)}(a,a,i.subarray(64,80),f,c),H(i,a[2],i),D(i,0,16),function(n,t){var r,e=t();for(I(e,n[0],n[1]),P(n[0],n[0],n[1]),D(n[0],0,16),D(e,0,16),J(n[1],e),D(n[1],0,16),D(n[1],0,16),D(n[0],n[0],n[1]),r=0;r<16;r++)n[0][r]=Math.round(n[0][r])}(a,i),j(a[0],a[0]),N(o,a[0]);for(var u=0;u<32;u++)o[u]^=128&o[31];for(e=0;e<32;e++)n[e+32]=o[e];for(e=0;e<32;e++)n[e]=r[e]}(r,n),{publicKey:r.subarray(32),secretKey:r}},n.sign.keyPair.fromSeed=function(n){if(32!==n.length)throw new Error("bad seed size");var t=new Uint8Array(64);return function(n,r){var e,o=new Uint8Array(64),i=new Float64Array(80),a=[t(),t(),t(),t()];for(e=0;e<64;e++)o[e]=r[e];!function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(o),o[0]&=248,o[31]&=127,o[31]|=64,C(i,o),O(i),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[0],i.subarray(0,16)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[1],i.subarray(16,32)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[2],i.subarray(32,48)),function(n,t){var r;for(r=0;r<16;r++)n[r]=t[r]}(a[3],i.subarray(48,64)),function(n,t,r,e,o){var a,u,c=t(),f=t(),s=t(),l=t(),h=t(),p=t(),y=t(),d=t(),g=t();for(I(c,n[1],n[0]),I(g,e[1],e[0]),D(c,0,16),D(g,0,16),I(f,n[0],n[1]),I(d,e[0],e[1]),D(f,0,16),D(d,0,16),D(s,c,d),D(l,f,g),I(h,s,l),P(p,s,l),D(y,r[2],o[2]),F(y,0,16),function(n,t){var r;for(r=0;r<16;r++)n[r]=2*t[r]}(y,y),I(d,r[3],o[3]),D(d,0,16),I(g,y,d),P(c,y,d),D(f,n[2],n[2]),G(s,0,0),D(l,s,p),D(s,h,g),D(y,h,c),D(d,l,c),D(g,p,g),a=t(),u=t(),I(a,s,y),I(u,d,g),j(n[0],a),j(n[1],u),I(a,l,g),I(u,s,d),j(n[2],a),j(n[3],u)}(a,a,i.subarray(64,80),f,c),H(i,a[2],i),D(i,0,16),function(n,t){var r,e=t();for(I(e,n[0],n[1]),P(n[0],n[0],n[1]),D(n[0],0,16),D(e,0,16),J(n[1],e),D(n[1],0,16),D(n[1],0,16),D(n[0],n[0],n[1]),r=0;r<16;r++)n[0][r]=Math.round(n[0][r])}(a,i),j(a[0],a[0]),N(t.subarray(32),a[0]);for(var u=0;u<32;u++)t[u+32]^=128&t[63];for(e=0;e<32;e++)t[e]=n[e]}(t,function(n){var t=new Uint8Array(64);return function(n,t){!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}(n);for(var r=0;r<64;r++)n[r]=t[r]}(t,n),t}(n)),{publicKey:t.subarray(32),secretKey:t}},n.sign.publicKeyLength=32,n.sign.secretKeyLength=64,n.sign.seedLength=32,n.sign.signatureLength=64,n.verify=function(n,t,r){var e;if(64!==t.length)throw new Error("bad signature size");if(32!==r.length)throw new Error("bad public key size");if(e=new Uint8Array(64+n.length),function(n,t){for(var r=0;r<t.length;r++)n[r]=t[r]}(e.subarray(0,64),t),function(n,t){for(var r=0;r<t.length;r++)n[r]=t[r]}(e.subarray(64),n),0!==Q(e,r))return!1;return!0},n.hash=function(n){var t=new Uint8Array(64);return function(n){var t,r=new Uint8Array(64);for(t=0;t<64;t++)r[t]=n[t];!function(n){var t,r,e,o,i,a,u,c,f,s=new Uint32Array(16),l=new Uint32Array(16);for(t=0;t<16;t++)s[t]=0,l[t]=0;for(t=0;t<64;t++)s[t>>2]|=n[t]<<(24-8*(3&t));s[0]+=1779033703,s[1]+=3144134277,s[2]+=1013904242,s[3]+=2773480762,s[4]+=1359893119,s[5]+=2600822924,s[6]+=528734635,s[7]+=1541459225;for(var h=0;h<80;h++){if(r=s[0],e=s[1],o=s[2],i=s[3],a=s[4],u=s[5],c=s[6],f=s[7],h<16)l[h]=s[h];else{var p=l[h-15],y=l[h-2];l[h]=(l[h-16]+(((p>>>7|p<<25)^(p>>>18|p<<14)^p>>>3)>>>0)+l[h-7]+(((y>>>17|y<<15)^(y>>>19|y<<13)^y>>>10)>>>0))>>>0}var d=((((a>>>6|a<<26)^(a>>>11|a<<21)^(a>>>25|a<<7))>>>0)+(a&u^~a&c)>>>0)+(f+(([1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298][h]>>>0)+l[h]>>>0)>>>0)>>>0,g=((((r>>>2|r<<30)^(r>>>13|r<<19)^(r>>>22|r<<10))>>>0)+(r&e^r&o^e&o)>>>0)>>>0;s[7]=s[6],s[6]=s[5],s[5]=s[4],s[4]=i+d>>>0,s[3]=s[2],s[2]=s[1],s[1]=s[0],s[0]=d+g>>>0}for(t=0;t<8;t++)s[t]=s[t]+[1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225][t]>>>0;for(t=0;t<8;t++)n[4*t]=s[t]>>>24,n[4*t+1]=s[t]>>>16&255,n[4*t+2]=s[t]>>>8&255,n[4*t+3]=255&s[t]}}(n),t=0;t<64;t++)n[t]=r[t]}(t),t},n.randomBytes=function(n){var t=new Uint8Array(n);return r(t),t},n.setPRNG=function(n){r=n},n}({});

  // Use Web Crypto for secure random
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    nacl.setPRNG(function(x) { crypto.getRandomValues(x); });
  }

  // =============================================================================
  // PBKDF2 Implementation (for seed phrase derivation)
  // =============================================================================
  async function pbkdf2(password, salt, iterations, keyLength) {
    const enc = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      typeof password === 'string' ? enc.encode(password) : password,
      'PBKDF2',
      false,
      ['deriveBits']
    );
    const bits = await crypto.subtle.deriveBits(
      {
        name: 'PBKDF2',
        salt: typeof salt === 'string' ? enc.encode(salt) : salt,
        iterations: iterations,
        hash: 'SHA-256'
      },
      keyMaterial,
      keyLength * 8
    );
    return new Uint8Array(bits);
  }

  // =============================================================================
  // SHA-256 Implementation (for address generation)
  // =============================================================================
  async function sha256(message) {
    const msgBuffer = typeof message === 'string' 
      ? new TextEncoder().encode(message) 
      : message;
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    return new Uint8Array(hashBuffer);
  }

  function bytesToHex(bytes) {
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function hexToBytes(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
    }
    return bytes;
  }

  // =============================================================================
  // RustChain Wallet
  // =============================================================================
  class RTCWallet {
    constructor(secretKey, publicKey) {
      this.secretKey = secretKey; // 64 bytes
      this.publicKey = publicKey; // 32 bytes
      this._address = null;
    }

    static async fromSeedPhrase(seedPhrase) {
      // Derive Ed25519 key using PBKDF2HMAC with RustChain-specific salt
      const seed = await pbkdf2(seedPhrase, 'rustchain-ed25519', 100000, 32);
      const keyPair = nacl.sign.keyPair.fromSeed(seed);
      return new RTCWallet(keyPair.secretKey, keyPair.publicKey);
    }

    static async fromPrivateKey(privateKeyHex) {
      const seed = hexToBytes(privateKeyHex);
      if (seed.length === 64) {
        // Full secret key
        return new RTCWallet(seed, seed.slice(32));
      } else if (seed.length === 32) {
        // Seed only
        const keyPair = nacl.sign.keyPair.fromSeed(seed);
        return new RTCWallet(keyPair.secretKey, keyPair.publicKey);
      }
      throw new Error('Invalid private key length');
    }

    async getAddress() {
      if (this._address) return this._address;
      const hash = await sha256(this.publicKey);
      this._address = 'RTC' + bytesToHex(hash).slice(0, 40);
      return this._address;
    }

    sign(message) {
      const msgBytes = typeof message === 'string' 
        ? new TextEncoder().encode(message) 
        : message;
      const signature = nacl.sign(msgBytes, this.secretKey);
      // Return only the signature (first 64 bytes), not message
      return signature.slice(0, 64);
    }

    getPublicKeyHex() {
      return bytesToHex(this.publicKey);
    }
  }

  // =============================================================================
  // AES-256-GCM Keystore Decryption
  // =============================================================================
  async function decryptKeystore(keystore, password) {
    const ks = typeof keystore === 'string' ? JSON.parse(keystore) : keystore;
    
    if (!ks.encrypted_seed || !ks.salt || !ks.nonce) {
      throw new Error('Invalid keystore format');
    }

    // Derive key from password
    const salt = hexToBytes(ks.salt);
    const key = await pbkdf2(password, salt, 100000, 32);
    
    // Import key for AES-GCM
    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      key,
      { name: 'AES-GCM' },
      false,
      ['decrypt']
    );

    // Decrypt
    const nonce = hexToBytes(ks.nonce);
    const ciphertext = hexToBytes(ks.encrypted_seed);
    
    try {
      const decrypted = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: nonce },
        cryptoKey,
        ciphertext
      );
      
      const seedPhrase = new TextDecoder().decode(decrypted);
      return RTCWallet.fromSeedPhrase(seedPhrase);
    } catch (e) {
      throw new Error('Incorrect password or corrupted keystore');
    }
  }

  // =============================================================================
  // RustChain Payment Widget
  // =============================================================================
  const DEFAULT_NODE = 'https://50.28.86.131';
  
  const CSS = `
    .rtc-pay-btn {
      background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: transform 0.2s, box-shadow 0.2s;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .rtc-pay-btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4);
    }
    .rtc-pay-btn:active {
      transform: translateY(0);
    }
    .rtc-pay-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }
    .rtc-pay-btn svg {
      width: 20px;
      height: 20px;
    }
    
    .rtc-modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 999999;
      animation: rtc-fade-in 0.2s ease;
    }
    @keyframes rtc-fade-in {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    
    .rtc-modal {
      background: #1a1a2e;
      border-radius: 16px;
      width: 90%;
      max-width: 420px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
      animation: rtc-slide-up 0.3s ease;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    @keyframes rtc-slide-up {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    
    .rtc-modal-header {
      padding: 20px 24px;
      border-bottom: 1px solid #2d2d44;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .rtc-modal-title {
      color: #fff;
      font-size: 18px;
      font-weight: 600;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .rtc-modal-close {
      background: none;
      border: none;
      color: #888;
      font-size: 24px;
      cursor: pointer;
      padding: 0;
      line-height: 1;
    }
    .rtc-modal-close:hover {
      color: #fff;
    }
    
    .rtc-modal-body {
      padding: 24px;
    }
    
    .rtc-payment-summary {
      background: #0d0d1a;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      text-align: center;
    }
    .rtc-payment-amount {
      font-size: 36px;
      font-weight: 700;
      color: #f97316;
      margin: 0;
    }
    .rtc-payment-label {
      color: #888;
      font-size: 14px;
      margin-top: 4px;
    }
    .rtc-payment-to {
      color: #666;
      font-size: 12px;
      margin-top: 12px;
      word-break: break-all;
    }
    
    .rtc-form-group {
      margin-bottom: 16px;
    }
    .rtc-form-label {
      display: block;
      color: #aaa;
      font-size: 13px;
      font-weight: 500;
      margin-bottom: 6px;
    }
    .rtc-form-input {
      width: 100%;
      padding: 12px 14px;
      background: #0d0d1a;
      border: 1px solid #2d2d44;
      border-radius: 8px;
      color: #fff;
      font-size: 14px;
      box-sizing: border-box;
      transition: border-color 0.2s;
    }
    .rtc-form-input:focus {
      outline: none;
      border-color: #f97316;
    }
    .rtc-form-input::placeholder {
      color: #555;
    }
    .rtc-form-textarea {
      min-height: 80px;
      resize: vertical;
      font-family: monospace;
    }
    
    .rtc-tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
    .rtc-tab {
      flex: 1;
      padding: 10px;
      background: #0d0d1a;
      border: 1px solid #2d2d44;
      border-radius: 8px;
      color: #888;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .rtc-tab:hover {
      border-color: #f97316;
      color: #fff;
    }
    .rtc-tab.active {
      background: #f97316;
      border-color: #f97316;
      color: #fff;
    }
    
    .rtc-btn-primary {
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
      border: none;
      border-radius: 8px;
      color: #fff;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .rtc-btn-primary:hover {
      opacity: 0.9;
    }
    .rtc-btn-primary:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    .rtc-error {
      background: #3d1515;
      border: 1px solid #f87171;
      color: #f87171;
      padding: 12px;
      border-radius: 8px;
      font-size: 13px;
      margin-bottom: 16px;
    }
    
    .rtc-success {
      text-align: center;
      padding: 20px 0;
    }
    .rtc-success-icon {
      width: 64px;
      height: 64px;
      background: #166534;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
    }
    .rtc-success-icon svg {
      width: 32px;
      height: 32px;
      color: #4ade80;
    }
    .rtc-success-title {
      color: #4ade80;
      font-size: 20px;
      font-weight: 600;
      margin: 0 0 8px;
    }
    .rtc-success-tx {
      color: #888;
      font-size: 12px;
      word-break: break-all;
    }
    
    .rtc-spinner {
      width: 20px;
      height: 20px;
      border: 2px solid #fff3;
      border-top-color: #fff;
      border-radius: 50%;
      animation: rtc-spin 0.8s linear infinite;
      display: inline-block;
    }
    @keyframes rtc-spin {
      to { transform: rotate(360deg); }
    }
    
    .rtc-file-input {
      display: none;
    }
    .rtc-file-label {
      display: block;
      padding: 12px 14px;
      background: #0d0d1a;
      border: 1px dashed #2d2d44;
      border-radius: 8px;
      color: #888;
      font-size: 14px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s;
    }
    .rtc-file-label:hover {
      border-color: #f97316;
    }
    .rtc-file-label.has-file {
      border-style: solid;
      border-color: #4ade80;
      color: #4ade80;
    }
  `;

  const LOGO_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
    <path d="M2 17l10 5 10-5"/>
    <path d="M2 12l10 5 10-5"/>
  </svg>`;

  const CHECK_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
    <polyline points="20 6 9 17 4 12"/>
  </svg>`;

  class RustChainPay {
    constructor(config = {}) {
      this.nodeUrl = config.nodeUrl || DEFAULT_NODE;
      this.onSuccess = config.onSuccess || (() => {});
      this.onError = config.onError || (() => {});
      this.onCancel = config.onCancel || (() => {});
      
      this._injectStyles();
    }

    _injectStyles() {
      if (document.getElementById('rtc-pay-styles')) return;
      const style = document.createElement('style');
      style.id = 'rtc-pay-styles';
      style.textContent = CSS;
      document.head.appendChild(style);
    }

    createButton(container, options = {}) {
      const el = typeof container === 'string' 
        ? document.querySelector(container) 
        : container;
      
      if (!el) {
        console.error('RustChain Pay: Container not found');
        return;
      }

      const config = {
        to: el.dataset.to || options.to,
        amount: parseFloat(el.dataset.amount || options.amount || 0),
        memo: el.dataset.memo || options.memo || '',
        label: el.dataset.label || options.label || `Pay ${el.dataset.amount || options.amount || ''} RTC`,
        callback: el.dataset.callback || options.callback
      };

      const btn = document.createElement('button');
      btn.className = 'rtc-pay-btn';
      btn.innerHTML = `${LOGO_SVG} ${config.label}`;
      btn.onclick = () => this.openPaymentModal(config);
      
      el.appendChild(btn);
      return btn;
    }

    openPaymentModal(config) {
      // Create modal
      const overlay = document.createElement('div');
      overlay.className = 'rtc-modal-overlay';
      
      overlay.innerHTML = `
        <div class="rtc-modal">
          <div class="rtc-modal-header">
            <h2 class="rtc-modal-title">${LOGO_SVG} RustChain Payment</h2>
            <button class="rtc-modal-close">&times;</button>
          </div>
          <div class="rtc-modal-body">
            <div class="rtc-payment-summary">
              <p class="rtc-payment-amount">${config.amount} RTC</p>
              <p class="rtc-payment-label">Payment Amount</p>
              ${config.memo ? `<p class="rtc-payment-to">Memo: ${config.memo}</p>` : ''}
              <p class="rtc-payment-to">To: ${config.to}</p>
            </div>
            
            <div class="rtc-error" style="display: none"></div>
            
            <div class="rtc-tabs">
              <button class="rtc-tab active" data-tab="seed">Seed Phrase</button>
              <button class="rtc-tab" data-tab="keystore">Keystore File</button>
            </div>
            
            <div class="rtc-tab-content" data-content="seed">
              <div class="rtc-form-group">
                <label class="rtc-form-label">24-Word Seed Phrase</label>
                <textarea class="rtc-form-input rtc-form-textarea" id="rtc-seed" 
                  placeholder="Enter your 24-word seed phrase..."></textarea>
              </div>
            </div>
            
            <div class="rtc-tab-content" data-content="keystore" style="display: none">
              <div class="rtc-form-group">
                <input type="file" class="rtc-file-input" id="rtc-keystore-file" accept=".json">
                <label class="rtc-file-label" for="rtc-keystore-file">
                  Click to select keystore file (.json)
                </label>
              </div>
              <div class="rtc-form-group">
                <label class="rtc-form-label">Keystore Password</label>
                <input type="password" class="rtc-form-input" id="rtc-keystore-password" 
                  placeholder="Enter your keystore password">
              </div>
            </div>
            
            <button class="rtc-btn-primary" id="rtc-submit">
              Sign & Send Payment
            </button>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);

      // Event handlers
      const modal = overlay.querySelector('.rtc-modal');
      const closeBtn = overlay.querySelector('.rtc-modal-close');
      const tabs = overlay.querySelectorAll('.rtc-tab');
      const tabContents = overlay.querySelectorAll('.rtc-tab-content');
      const submitBtn = overlay.querySelector('#rtc-submit');
      const errorDiv = overlay.querySelector('.rtc-error');
      const fileInput = overlay.querySelector('#rtc-keystore-file');
      const fileLabel = overlay.querySelector('.rtc-file-label');

      let keystoreData = null;
      let activeTab = 'seed';

      const close = () => {
        overlay.remove();
        this.onCancel();
      };

      closeBtn.onclick = close;
      overlay.onclick = (e) => {
        if (e.target === overlay) close();
      };

      tabs.forEach(tab => {
        tab.onclick = () => {
          activeTab = tab.dataset.tab;
          tabs.forEach(t => t.classList.toggle('active', t === tab));
          tabContents.forEach(c => {
            c.style.display = c.dataset.content === activeTab ? 'block' : 'none';
          });
        };
      });

      fileInput.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (evt) => {
            try {
              keystoreData = JSON.parse(evt.target.result);
              fileLabel.textContent = `✓ ${file.name}`;
              fileLabel.classList.add('has-file');
            } catch (err) {
              this._showError(errorDiv, 'Invalid keystore file');
              keystoreData = null;
            }
          };
          reader.readAsText(file);
        }
      };

      submitBtn.onclick = async () => {
        errorDiv.style.display = 'none';
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="rtc-spinner"></span> Processing...';

        try {
          let wallet;

          if (activeTab === 'seed') {
            const seed = overlay.querySelector('#rtc-seed').value.trim();
            if (!seed || seed.split(/\s+/).length < 12) {
              throw new Error('Please enter a valid seed phrase (12-24 words)');
            }
            wallet = await RTCWallet.fromSeedPhrase(seed);
          } else {
            if (!keystoreData) {
              throw new Error('Please select a keystore file');
            }
            const password = overlay.querySelector('#rtc-keystore-password').value;
            if (!password) {
              throw new Error('Please enter your keystore password');
            }
            wallet = await decryptKeystore(keystoreData, password);
          }

          const result = await this._sendPayment(wallet, config);
          this._showSuccess(overlay, result);
          this.onSuccess(result);

          if (config.callback) {
            this._notifyCallback(config.callback, result);
          }

        } catch (err) {
          this._showError(errorDiv, err.message);
          submitBtn.disabled = false;
          submitBtn.innerHTML = 'Sign & Send Payment';
        }
      };
    }

    async _sendPayment(wallet, config) {
      const fromAddress = await wallet.getAddress();
      const timestamp = Math.floor(Date.now() / 1000);
      const nonce = Array.from(crypto.getRandomValues(new Uint8Array(16)))
        .map(b => b.toString(16).padStart(2, '0')).join('');

      const transferData = {
        from_address: fromAddress,
        to_address: config.to,
        amount_rtc: config.amount,
        timestamp: timestamp,
        nonce: nonce,
        memo: config.memo || ''
      };

      // Sign the transfer (JSON with sorted keys)
      const message = JSON.stringify(transferData, Object.keys(transferData).sort());
      const signature = wallet.sign(message);

      // Submit to chain
      const response = await fetch(`${this.nodeUrl}/wallet/transfer/signed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...transferData,
          signature: bytesToHex(signature),
          public_key: wallet.getPublicKeyHex()
        })
      });

      if (!response.ok) {
        const error = await response.text();
        let errorMsg = 'Payment failed';
        try {
          const errJson = JSON.parse(error);
          errorMsg = errJson.error || errJson.message || errorMsg;
        } catch (e) {
          errorMsg = error || errorMsg;
        }
        throw new Error(errorMsg);
      }

      const result = await response.json();
      return {
        tx_hash: result.tx_hash || result.hash,
        from: fromAddress,
        to: config.to,
        amount: config.amount,
        memo: config.memo,
        timestamp: timestamp
      };
    }

    _showError(errorDiv, message) {
      errorDiv.textContent = message;
      errorDiv.style.display = 'block';
    }

    _showSuccess(overlay, result) {
      const body = overlay.querySelector('.rtc-modal-body');
      body.innerHTML = `
        <div class="rtc-success">
          <div class="rtc-success-icon">${CHECK_SVG}</div>
          <h3 class="rtc-success-title">Payment Successful!</h3>
          <p class="rtc-success-tx">TX: ${result.tx_hash}</p>
        </div>
        <button class="rtc-btn-primary" onclick="this.closest('.rtc-modal-overlay').remove()">
          Done
        </button>
      `;
    }

    async _notifyCallback(callbackUrl, result) {
      try {
        await fetch(callbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(result)
        });
      } catch (e) {
        console.warn('RustChain Pay: Callback notification failed', e);
      }
    }

    async checkBalance(address) {
      const response = await fetch(`${this.nodeUrl}/wallet/balance?miner_id=${encodeURIComponent(address)}`);
      if (!response.ok) throw new Error('Failed to fetch balance');
      return response.json();
    }
  }

  // =============================================================================
  // Auto-initialize widgets
  // =============================================================================
  function autoInit() {
    const widgets = document.querySelectorAll('[data-rtc-pay], #rtc-pay, .rtc-pay');
    if (widgets.length === 0) return;

    const rtcPay = new RustChainPay();
    widgets.forEach(el => rtcPay.createButton(el));
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInit);
  } else {
    autoInit();
  }

  // Export
  global.RustChainPay = RustChainPay;
  global.RTCWallet = RTCWallet;

})(typeof window !== 'undefined' ? window : this);
