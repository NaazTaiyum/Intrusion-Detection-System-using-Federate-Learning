#include <stdio.h>
#include <string.h>

int main()
{
    int N;
    scanf("%d", &N);

    char s[1200];

    while (N--)
    {
        scanf("%s", s);

        int le = 0;
        int nl = -1;

        for (int i = 0; s[i];)
        {
            if (s[i] == '\\' && s[i + 1] == '0')
            {
                if (nl == -1)
                    nl = le;
                le++;
                i += 2;
            }
            else
            {
                le++;
                i++;
            }
        }

        int sv = le + 1;
        int stv = (nl == -1 ? le : nl);

        printf("%d %d\n", sv, stv);
    }

    return 0;
}
