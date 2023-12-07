/**
 *  @brief      Postgres bindings for USearch.
 *  @file       lib_sqlite.cpp
 *  @author     Ash Vardanian
 *  @date       November 28, 2023
 *  @copyright  Copyright (c) 2023
 *
 *  https://www.postgresql.org/docs/current/xfunc-c.html
 */
#include <postgres.h>

#include <fmgr.h> // `PG_FUNCTION_INFO_V1`

#include <stringzilla/stringzilla.h>

PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(copytext);

Datum copytext(PG_FUNCTION_ARGS) {
    text* t = PG_GETARG_TEXT_PP(0);

    /*
     * VARSIZE_ANY_EXHDR is the size of the struct in bytes, minus the
     * VARHDRSZ or VARHDRSZ_SHORT of its header.  Construct the copy with a
     * full-length header.
     */
    text* new_t = (text*)palloc(VARSIZE_ANY_EXHDR(t) + VARHDRSZ);
    SET_VARSIZE(new_t, VARSIZE_ANY_EXHDR(t) + VARHDRSZ);

    /*
     * VARDATA is a pointer to the data region of the new struct.  The source
     * could be a short datum, so retrieve its data through VARDATA_ANY.
     */
    memcpy(VARDATA(new_t),        /* destination */
           VARDATA_ANY(t),        /* source */
           VARSIZE_ANY_EXHDR(t)); /* how many bytes */
    PG_RETURN_TEXT_P(new_t);
}
