/*
 * ps3recomp game project -- game-specific hooks and overrides.
 *
 * main.cpp is the runner and is game-agnostic. This file is where a port puts
 * everything that is not: the PRX loading hook it must answer, overrides for
 * firmware functions the HLE library gets wrong for this title, and patches
 * over recompiled code.
 *
 * It starts out as the empty version of all of that, which is what a game with
 * no lifted PRX and no overrides needs.
 */

#include <cstdio>
#include <cstring>
#include <cstdlib>

#include "ps3emu/ps3types.h"
#include "ps3emu/error_codes.h"

/* ---------------------------------------------------------------------------
 * PRX loading
 *
 * main.cpp calls this once, after the lifted function table is registered and
 * vm_base is live, before the game runs. A title that lifts a real system PRX
 * -- libsre, which is cellSpurs and cellSync -- loads its image into guest RAM
 * here and registers its exports. Most ports never need to: the HLE library
 * answers those modules instead.
 * -----------------------------------------------------------------------*/

extern "C" void ps3_load_prx_modules(void)
{
}

/* ---------------------------------------------------------------------------
 * Example: Override a specific NID
 *
 * The module system resolves function imports by NID.  To replace a default
 * HLE stub with custom logic, register your function at init time.
 * -----------------------------------------------------------------------*/

/*
 * Example: override cellGcmSetFlipMode (NID 0xA53D12AE) to force vsync.
 *
 *   static void my_cellGcmSetFlipMode(u32 mode)
 *   {
 *       printf("[hook] cellGcmSetFlipMode: forcing VSYNC (was %u)\n", mode);
 *       // Force vsync regardless of what the game requested
 *       cellGcmSetFlipMode(CELL_GCM_DISPLAY_VSYNC);
 *   }
 *
 * Then in your init code:
 *
 *   ps3::modules::override_nid(0xA53D12AE,
 *       reinterpret_cast<void*>(my_cellGcmSetFlipMode));
 */

/* ---------------------------------------------------------------------------
 * Example: Hook into module loading
 *
 * You can intercept cellSysmoduleLoadModule to perform custom actions
 * when a particular module is loaded.
 * -----------------------------------------------------------------------*/

/*
 *   static s32 my_loadmodule_hook(u16 id)
 *   {
 *       printf("[hook] Module 0x%04X loaded\n", id);
 *
 *       if (id == CELL_SYSMODULE_AUDIO) {
 *           // Perform custom audio backend initialization
 *           init_my_audio_backend();
 *       }
 *
 *       // Call the original implementation
 *       return cellSysmoduleLoadModule(id);
 *   }
 */

/* ---------------------------------------------------------------------------
 * Game-specific patches
 *
 * Sometimes you need to patch recompiled code at specific addresses.
 * Use the patch system to modify behavior without editing generated code.
 * -----------------------------------------------------------------------*/

/*
 *   // Skip an integrity check at guest address 0x00812FA0
 *   ps3::patches::nop_range(0x00812FA0, 0x00812FB0);
 *
 *   // Replace a function call with a direct return
 *   ps3::patches::force_return(0x009A1000, 0);  // return 0
 */

/* ---------------------------------------------------------------------------
 * Saint Seiya Brave Soldiers: imports the HLE library does not answer
 *
 * main.cpp calls game_register_hle() right after ppu_hle_init(), so these
 * replace the "unresolved NID" fallback, which writes no out-params.
 * -----------------------------------------------------------------------*/

#include "ppu_recomp.h"   /* ppu_context */

extern "C" void ps3_hle_register_ctx(uint32_t nid, const char* name, void (*fn)(ppu_context*));
extern "C" void vm_write32(uint64_t a, uint32_t v);

/* SPURS JobQueue, Port2 interface. The library's JobQueue completes every job
 * on push (libs/spurs/cellSpursJq.c). These run the job synchronously on the
 * pushing thread when its binary has a lifted image registered (same path as
 * the job-chain walker), so a later Sync sees it finished. Without a lifted
 * image the job is dropped; SPU_DUMP_MISS=<dir> writes the binary out for
 * lifting. JQ_RUN=0 turns execution off. */
extern "C" uint32_t vm_read32(uint64_t a);
extern "C" int spu_workload_dispatch_job(const uint8_t* image, uint32_t image_size,
                                         uint32_t job_ea, uint32_t job_desc_size);
extern "C" uint8_t* vm_base;

static void jq_run(ppu_context* ctx)
{
    static int en = -1;
    if (en < 0) { const char* e = getenv("JQ_RUN"); en = e ? atoi(e) : 1; }
    uint32_t job = (uint32_t)ctx->gpr[4], size = (uint32_t)ctx->gpr[5];
    if (!en || !job) return;
    uint32_t ea_bin   = vm_read32(job + 4) & ~7u;                 /* low word of eaBinary */
    uint32_t size_bin = ((vm_read32(job + 8) >> 16) & 0xFFFFu) << 4;
    if (!ea_bin || !size_bin || ea_bin >= 0x10000000u) return;
    spu_workload_dispatch_job(vm_base + ea_bin, size_bin, job, size);
}

/* JQ_DBG=<N>: log the first N pushed jobs (descriptor words) and a running count. */
static void jq_log(const char* what, ppu_context* ctx)
{
    static int cap = -1, n = 0;
    if (cap < 0) { const char* e = getenv("JQ_DBG"); cap = e ? atoi(e) : 0; }
    if (!cap) return;
    n++;
    uint32_t job = (uint32_t)ctx->gpr[4], size = (uint32_t)ctx->gpr[5];
    if (n <= cap) {
        fprintf(stderr, "[JQ] %s #%d port=0x%08X job=0x%08X size=%u tag=%u lr=0x%08X:", what, n,
                (uint32_t)ctx->gpr[3], job, size, (uint32_t)ctx->gpr[6], (uint32_t)ctx->lr);
        for (uint32_t i = 0; i < 16 && job; i++) fprintf(stderr, " %08X", vm_read32(job + i * 4));
        fprintf(stderr, "\n");
    } else if ((n % 1000) == 0) fprintf(stderr, "[JQ] %d pushes\n", n);
}

static void jq_port2_sync(ppu_context* ctx)       { ctx->gpr[3] = CELL_OK; }  /* (port, mask) */
static void jq_port2_push_body(ppu_context* ctx)  { jq_log("push", ctx); jq_run(ctx); ctx->gpr[3] = CELL_OK; }  /* (port, job, size, tag, sync) */
static void jq_port2_copy_push(ppu_context* ctx)  { jq_log("copypush", ctx); jq_run(ctx); ctx->gpr[3] = CELL_OK; }  /* (port, job, size, tag, sync) */

/* cellFontInitLibraryFreeTypeWithRevision(u64 revision, const CellFontLibraryConfigFT* config,
 * const CellFontLibrary** lib). The HLE font calls ignore the library handle, but the
 * game keeps it and checks it for null, so hand back the config's address: valid,
 * non-null guest memory the game never writes through. */
static void font_init_freetype_rev(ppu_context* ctx)
{
    uint32_t config = (uint32_t)ctx->gpr[4], lib = (uint32_t)ctx->gpr[5];
    if (!lib) { ctx->gpr[3] = (uint64_t)(int64_t)(int32_t)0x80540002; return; }  /* CELL_FONT_ERROR_INVALID_PARAMETER */
    vm_write32(lib, config ? config : 1u);
    ctx->gpr[3] = CELL_OK;
}
static void font_ok(ppu_context* ctx) { ctx->gpr[3] = CELL_OK; }  /* SetResolutionDpi, SetScalePoint */

/* Present once per guest flip. Brave Soldiers clears a display buffer in the
 * middle of its frame, so the backend's clear-boundary present showed the
 * offscreen passes plus composite, and the flip present showed only the last
 * two draws: two half frames per flip, which flickered against black.
 * RSX_ACCUM_FRAME=0 in the environment restores the clear-boundary present. */
static void game_env_defaults(void)
{
    if (!getenv("RSX_ACCUM_FRAME")) {
#ifdef _WIN32
        _putenv_s("RSX_ACCUM_FRAME", "1");
#else
        setenv("RSX_ACCUM_FRAME", "1", 0);
#endif
    }
}

extern "C" void game_register_hle(void)
{
    game_env_defaults();
    ps3_hle_register_ctx(0xFACB3CEDu, "cellSpursJobQueuePort2Sync",              jq_port2_sync);
    ps3_hle_register_ctx(0xCF89F218u, "_cellSpursJobQueuePort2PushJobBody",      jq_port2_push_body);
    ps3_hle_register_ctx(0xC39173A4u, "_cellSpursJobQueuePort2CopyPushJobBody",  jq_port2_copy_push);
    ps3_hle_register_ctx(0x7A0A83C4u, "cellFontInitLibraryFreeTypeWithRevision", font_init_freetype_rev);
    ps3_hle_register_ctx(0xFB3341BAu, "cellFontSetResolutionDpi",                font_ok);
    ps3_hle_register_ctx(0x70F3E728u, "cellFontSetScalePoint",                   font_ok);
}
