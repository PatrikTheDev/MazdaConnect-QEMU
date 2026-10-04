/* Check the mounted ARMEL libm contract; this is not a performance benchmark. */
#include <fenv.h>
#include <math.h>
#include <stdio.h>

int main(void) {
    const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    const char *names[]={"nearest","downward","upward","towardzero"};
    const float input[]={0.5f,1.5f,-1.5f};
    const float expected[][3]={{0,2,-2},{0,1,-2},{1,2,-1},{0,1,-1}};
    float (*volatile round_value)(float)=nearbyintf;
    int original=fegetround(), failures=0;
    if (original<0) return 2;
    for (unsigned mode=0;mode<4;++mode) {
        if (fesetround(modes[mode]) || fegetround()!=modes[mode]) {
            fprintf(stderr,"Cannot select rounding mode %s\n",names[mode]);
            fesetround(original); return 2;
        }
        for (unsigned i=0;i<3;++i) {
            feclearexcept(FE_ALL_EXCEPT);
            float result=round_value(input[i]);
            int inexact=fetestexcept(FE_INEXACT);
            int ok=result==expected[mode][i] && !inexact;
            printf("%s input=%a result=%a expected=%a inexact=%d %s\n",
                   names[mode],(double)input[i],(double)result,
                   (double)expected[mode][i],inexact,ok ? "PASS" : "FAIL");
            failures+=!ok;
        }
    }
    if (fesetround(original)) return 2;
    printf("nearbyintf rounding contract: %d/12 checks passed\n",12-failures);
    return failures ? 1 : 0;
}
