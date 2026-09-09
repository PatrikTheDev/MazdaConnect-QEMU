/* EU 74.00.324A MMUI-only opt-in patch. Addresses are checked by the builder.
 * Keep every original handler operation. Remember real system notifications;
 * after completed playback, resume Disclaimer only from IntroAnimation/Normal.
 */
.syntax unified
.arm
.text
.global state_hook, finish_hook
state_hook:
    push {r0, ip}
    ldr ip, .Lstate_delta
.Lstate_pc:
    add ip, pc, ip
    str r2, [ip]
    pop {r0, ip}
    push {r4, r5, lr}  /* displaced first instruction */
    b state_continue
.Lstate_delta:
    .word state_storage - (.Lstate_pc + 8)

finish_hook:
    push {r4, r5, r6, lr}
    sub sp, sp, #8
    ldr ip, [sp, #24]  /* forward the original fifth argument */
    str ip, [sp]
    mov r4, r1
    bl set_app_context
    mov r5, r0
    ldr r0, [r4, #4]
    movw r1, #1023     /* current MMUI context: IntroAnimation */
    cmp r0, r1
    bne .Ldone
    ldr ip, .Lfinish_delta
.Lfinish_pc:
    add ip, pc, ip
    ldr r0, [ip]
    cmp r0, #2        /* latest original system notification: Normal */
    bne .Ldone
    movw r0, #1491    /* original ShowDisclaimer event */
    mov r1, #1
    bl send_event
.Ldone:
    mov r0, r5
    add sp, sp, #8
    pop {r4, r5, r6, pc}
.Lfinish_delta:
    .word state_storage - (.Lfinish_pc + 8)
.section .note.GNU-stack,"",%progbits
