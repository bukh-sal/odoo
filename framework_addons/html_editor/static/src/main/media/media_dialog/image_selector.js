import { useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { getCSSVariableValue, getHtmlStyle } from "@html_editor/utils/formatting";
import { Attachment, FileSelector, IMAGE_EXTENSIONS, IMAGE_MIMETYPES } from "./file_selector";
import { isSrcCorsProtected } from "@html_editor/utils/image";

export class AutoResizeImage extends Attachment {
    static template = "html_editor.AutoResizeImage";
    setup() {
        super.setup();

        this.image = useRef("auto-resize-image");
        this.container = useRef("auto-resize-image-container");

        this.state = useState({
            loaded: false,
        });
    }

    async onImageLoaded() {
        if (!this.image.el) {
            // Do not fail if already removed.
            return;
        }
        if (this.props.onLoaded) {
            await this.props.onLoaded(this.image.el);
            if (!this.image.el) {
                // If replaced by colored version, aspect ratio will be
                // computed on it instead.
                return;
            }
        }
        const aspectRatio = this.image.el.offsetWidth / this.image.el.offsetHeight;
        const width = aspectRatio * this.props.minRowHeight;
        this.container.el.style.flexGrow = width;
        this.container.el.style.flexBasis = `${width}px`;
        this.state.loaded = true;
    }
}
const newLocal = "img-fluid";
export class ImageSelector extends FileSelector {
    static mediaSpecificClasses = ["img", newLocal, "o_we_custom_image"];
    static mediaSpecificStyles = ["transform", "width"];
    static mediaExtraClasses = [
        "rounded-circle",
        "rounded",
        "img-thumbnail",
        "shadow",
        "w-25",
        "w-50",
        "w-75",
        "w-100",
    ];
    static tagNames = ["IMG"];
    static attachmentsListTemplate = "html_editor.ImagesListTemplate";
    static components = {
        ...FileSelector.components,
        AutoResizeImage,
    };

    setup() {
        super.setup();


        this.state.showOptimized = false;

        this.uploadText = _t("Upload an image");
        this.urlPlaceholder = "https://example.com/image.png";
        this.addText = _t("Add URL");
        this.searchPlaceholder = _t("Search an image");
        this.urlWarningTitle = _t(
            "Uploaded image's format is not supported. Try with: " + IMAGE_EXTENSIONS.join(", ")
        );
        this.allLoadedText = _t("All images have been loaded");
        this.showOptimizedOption = this.env.debug;
        this.MIN_ROW_HEIGHT = 128;

        this.fileMimetypes = IMAGE_MIMETYPES.join(",");
        this.isImageField =
            !!this.props.media?.closest("[data-oe-type=image]") || !!this.props.addFieldImage;
        this.isProcessingClick = false;
    }






    get attachmentsDomain() {
        const domain = super.attachmentsDomain;
        domain.push(["mimetype", "in", IMAGE_MIMETYPES]);
        domain.push("!", ["name", "=like", "%.crop"]);
        domain.push("|", ["type", "=", "binary"], "!", ["url", "=like", "/%/static/%"]);

        // Optimized images (meaning they are related to an `original_id`) can
        // only be shown in debug mode as the toggler to make those images
        // appear is hidden when not in debug mode.
        // There is thus no point to fetch those optimized images outside debug
        // mode. Worst, it leads to bugs: it might fetch only optimized images
        // when clicking on "load more" which will look like it's bugged as no
        // images will appear on screen (they all will be hidden).
        if (!this.env.debug) {
            const subDomain = [false];

            // Particular exception: if the edited image is an optimized
            // image, we need to fetch it too so it's displayed as the
            // selected image when opening the media dialog.
            // We might get a few more optimized image than necessary if the
            // original image has multiple optimized images but it's not a
            // big deal.
            const originalId = this.props.media && this.props.media.dataset.originalId;
            if (originalId) {
                subDomain.push(originalId);
            }

            domain.push(["original_id", "in", subDomain]);
        }

        return domain;
    }

    async uploadFiles(files) {
        let abortFn;

        const uploadPromise = this.uploadService.uploadFiles(
            files,
            {
                resModel: this.props.resModel,
                resId: this.props.resId,
                isImage: true,
            },
            (attachment) => this.onUploaded(attachment),
            (abort) => {
                abortFn = abort;
            }
        );
        this.props.setAbortUploadsCallback(() => abortFn?.());
        await uploadPromise;
    }

    async validateUrl(...args) {
        const { isValidUrl, path } = super.validateUrl(...args);
        const isValidFileFormat =
            isValidUrl &&
            (await new Promise((resolve) => {
                const img = new Image();
                img.src = path;
                img.onload = () => resolve(true);
                img.onerror = () => resolve(false);
            }));
        return { isValidFileFormat, isValidUrl };
    }

    async onLoadUploadedUrl(url, resolve) {
        const urlPathname = new URL(url, window.location.href).pathname;
        const imageExtension = IMAGE_EXTENSIONS.find((format) => urlPathname.endsWith(format));
        if (this.isImageField && imageExtension === ".webp") {
            // Do not allow the user to replace an image field by a
            // webp CORS protected image as we are not currently
            // able to manage the report creation if such images are
            // in there (as the equivalent jpeg can not be
            // generated). It also causes a problem for resize
            // operations as 'libwep' can not be used.
            this.notificationService.add(
                _t(
                    "You can not replace a field by this image. If you want to use this image, first save it on your computer and then upload it here."
                ),
                {
                    type: "danger",
                    sticky: true,
                }
            );
            return resolve();
        }
        super.onLoadUploadedUrl(url, resolve);
    }

    isInitialMedia(attachment) {
        if (this.props.media.dataset.originalSrc) {
            return this.props.media.dataset.originalSrc === attachment.image_src;
        }
        return this.props.media.getAttribute("src") === attachment.image_src;
    }

    async fetchAttachments(limit, offset) {
        const attachments = await super.fetchAttachments(limit, offset);
        if (this.isImageField) {
            // The image is a field; mark the attachments if they are linked to
            // a webp CORS protected image. Indeed, in this case, they should
            // not be selectable on the media dialog (due to a problem of image
            // resize and report creation).
            for (const attachment of attachments) {
                if (
                    attachment.mimetype === "image/webp" &&
                    (await isSrcCorsProtected(attachment.image_src))
                ) {
                    attachment.unselectable = true;
                }
            }
        }
        // Color-substitution for dynamic SVG attachment
        const primaryColors = {};
        const htmlStyle = getHtmlStyle(document);
        for (let color = 1; color <= 5; color++) {
            primaryColors[color] = getCSSVariableValue("o-color-" + color, htmlStyle);
        }
        return attachments.map((attachment) => {
            if (attachment.image_src.startsWith("/")) {
                const newURL = new URL(attachment.image_src, window.location.origin);
                // Set the main colors of dynamic SVGs to o-color-1~5
                if (
                    attachment.image_src.startsWith("/html_editor/shape/") ||
                    attachment.image_src.startsWith("/web_editor/shape/")
                ) {
                    newURL.searchParams.forEach((value, key) => {
                        const match = key.match(/^c([1-5])$/);
                        if (match) {
                            newURL.searchParams.set(key, primaryColors[match[1]]);
                        }
                    });
                } else {
                    // Set height so that db images load faster
                    newURL.searchParams.set("height", 2 * this.MIN_ROW_HEIGHT);
                }
                attachment.thumbnail_src = newURL.pathname + newURL.search;
            }
            if (this.selectInitialMedia() && this.isInitialMedia(attachment)) {
                this.selectAttachment(attachment);
            }
            return attachment;
        });
    }




    async onClickAttachment(attachment) {
        if (this.isProcessingClick) {
            return;
        }
        this.isProcessingClick = true;
        if (attachment.unselectable) {
            this.notificationService.add(
                _t(
                    "You can not replace a field by this image. If you want to use this image, first save it on your computer and then upload it here."
                ),
                {
                    type: "danger",
                    sticky: true,
                }
            );
            return;
        }
        this.selectAttachment(attachment);
        if (!this.props.multiSelect) {
            await this.props.save();
        }
        // The use of requestAnimationFrame is not ideal but we do it as a
        // temporary fix as the media dialog will be refactored
        requestAnimationFrame(() => {
            this.isProcessingClick = false;
        });
    }


    /**
     * Utility method used by the MediaDialog component.
     */
    static async createElements(selectedMedia, { orm }) {
        const selected = selectedMedia
            .filter((media) => media.mediaType === "attachment")
            .map((attachment) => {
                // Color-customize dynamic SVGs with the theme colors
                if (
                    attachment.image_src &&
                    (attachment.image_src.startsWith("/html_editor/shape/") ||
                        attachment.image_src.startsWith("/web_editor/shape/"))
                ) {
                    const colorCustomizedURL = new URL(
                        attachment.image_src,
                        window.location.origin
                    );
                    const htmlStyle = getHtmlStyle(document);
                    colorCustomizedURL.searchParams.forEach((value, key) => {
                        const match = key.match(/^c([1-5])$/);
                        if (match) {
                            colorCustomizedURL.searchParams.set(
                                key,
                                getCSSVariableValue(`o-color-${match[1]}`, htmlStyle)
                            );
                        }
                    });
                    attachment.image_src = colorCustomizedURL.pathname + colorCustomizedURL.search;
                }
                return attachment;
            });
        return Promise.all(
            selected.map(async (attachment) => {
                const imageEl = document.createElement("img");
                let src = attachment.image_src;
                if (!attachment.public && !attachment.url) {
                    let accessToken = attachment.access_token;
                    if (!accessToken) {
                        [accessToken] = await orm.call("ir.attachment", "generate_access_token", [
                            attachment.id,
                        ]);
                    }
                    src += `?access_token=${encodeURIComponent(accessToken)}`;
                }
                imageEl.src = src;
                imageEl.alt = attachment.description || "";
                imageEl.dataset.attachmentId = attachment.id;
                return imageEl;
            })
        );
    }

    async onImageLoaded(imgEl, attachment) {
        this.debouncedScrollUpdate();
    }

    /**
     * This converts the colors of an svg coming from the media library to
     * the palette's ones, and make them dynamic.
     *
     * @param {HTMLElement} imgEl
     * @param {Object} media
     * @returns
     */
}
