# Multiple Pixel IDs

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use multiple Pixel IDs when the same website measures conversions for more than
one advertiser, brand, or integration partner. Install the
[JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel) once, initialize each Pixel ID, and
choose whether to send each event to all pixels or only one.

## Initialize multiple pixels

Call `oaiq("init", ...)` for each Pixel ID:

```typescript
oaiq("init", { pixelId: "<PIXEL-ID-A>" });
oaiq("init", { pixelId: "<PIXEL-ID-B>" });
```


Load the SDK only once, and initialize each pixel before sending events to it.

## Send an event to every pixel

The `measure` command sends an event to every Pixel ID initialized at the time
of the call:

```typescript
oaiq("measure", "page_viewed", {
  type: "contents",
});
```


Both `<PIXEL-ID-A>` and `<PIXEL-ID-B>` receive the event. A pixel you initialize
later doesn't receive earlier events.

## Send an event to one pixel

Use `measureSingle` to send an event only to a specified Pixel ID:

```typescript
oaiq("measureSingle", "<PIXEL-ID-A>", "order_created", {
  type: "contents",
  amount: 2599,
  currency: "USD",
});
```


Only `<PIXEL-ID-A>` receives this event. `<PIXEL-ID-B>` doesn't receive it.

`measureSingle` accepts the same event data and optional event options as
`measure`, with the Pixel ID inserted before the event name:

```typescript
oaiq("measureSingle", pixelId, eventName, eventData, eventOptions);
```


Initialize the target Pixel ID before calling `measureSingle`. The SDK doesn't
send events for an unknown Pixel ID to another pixel.

For event names, event data, custom events, and event options, see
[Send events](https://developers.openai.com/ads/measurement-pixel#send-events).